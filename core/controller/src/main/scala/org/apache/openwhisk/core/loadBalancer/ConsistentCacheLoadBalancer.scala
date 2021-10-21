/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.apache.openwhisk.core.loadBalancer

import akka.actor.ActorRef
import akka.actor.ActorRefFactory

import akka.actor.{Actor, ActorSystem, Props}
import akka.cluster.ClusterEvent._
import akka.cluster.{Cluster, Member, MemberStatus}
import akka.management.scaladsl.AkkaManagement
import akka.management.cluster.bootstrap.ClusterBootstrap
// import akka.stream.ActorMaterializer
import org.apache.kafka.clients.producer.RecordMetadata
import pureconfig._
import pureconfig.generic.auto._
import org.apache.openwhisk.common._
import org.apache.openwhisk.core.WhiskConfig._
import org.apache.openwhisk.core.connector._
import org.apache.openwhisk.core.entity._
import org.apache.openwhisk.common.LoggingMarkers._
// import org.apache.openwhisk.core.loadBalancer.InvokerState.{Healthy, Offline, Unhealthy, Unresponsive}
import org.apache.openwhisk.core.{ConfigKeys, WhiskConfig}
import org.apache.openwhisk.spi.SpiLoader

import scala.concurrent.Future
import scala.collection.JavaConverters._
import java.util.concurrent.atomic.AtomicInteger
import scala.math.{min} //, max}
import scala.collection.mutable

import org.ishugaliy.allgood.consistent.hash.{HashRing, ConsistentHash}
import org.ishugaliy.allgood.consistent.hash.node.{Node}
import redis.clients.jedis.{Jedis}
import spray.json._
import org.apache.openwhisk.common.RedisPacketProtocol._

/**
 * A loadbalancer that schedules workload based on power-of-two consistent hashing-algorithm.
 */
class ConsistentCacheLoadBalancer(
  config: WhiskConfig,
  controllerInstance: ControllerInstanceId,
  feedFactory: FeedFactory,
  val invokerPoolFactory: InvokerPoolFactory,
  implicit val messagingProvider: MessagingProvider = SpiLoader.get[MessagingProvider])(
  implicit actorSystem: ActorSystem,
  logging: Logging)
    extends CommonLoadBalancer(config, feedFactory, controllerInstance) {

  /** Build a cluster of all loadbalancers */
  private val cluster: Option[Cluster] = if (loadConfigOrThrow[ClusterConfig](ConfigKeys.cluster).useClusterBootstrap) {
    AkkaManagement(actorSystem).start()
    ClusterBootstrap(actorSystem).start()
    Some(Cluster(actorSystem))
  } else if (loadConfigOrThrow[Seq[String]]("akka.cluster.seed-nodes").nonEmpty) {
    Some(Cluster(actorSystem))
  } else {
    None
  }

  override def emitMetrics() = {
    MetricEmitter.emitGaugeMetric(LOADBALANCER_ACTIVATIONS_INFLIGHT(controllerInstance), totalActivations.longValue)
    MetricEmitter.emitGaugeMetric(
      LOADBALANCER_MEMORY_INFLIGHT(controllerInstance, ""),
      totalBlackBoxActivationMemory.longValue + totalManagedActivationMemory.longValue)
    MetricEmitter.emitGaugeMetric(
      LOADBALANCER_MEMORY_INFLIGHT(controllerInstance, "Blackbox"),
      totalBlackBoxActivationMemory.longValue)
    MetricEmitter.emitGaugeMetric(
      LOADBALANCER_MEMORY_INFLIGHT(controllerInstance, "Managed"),
      totalManagedActivationMemory.longValue)
  }

  /** State needed for scheduling. */
  val schedulingState = ConsistentCacheLoadBalancerState()(lbConfig)

  /**
   * Monitors invoker supervision and the cluster to update the state sequentially
   *
   * All state updates should go through this actor to guarantee that
   * [[ConsistentCacheLoadBalancerState.updateInvokers]] and [[ConsistentCacheLoadBalancerState.updateCluster]]
   * are called exclusive of each other and not concurrently.
   */
  private val monitor = actorSystem.actorOf(Props(new Actor {
    override def preStart(): Unit = {
      cluster.foreach(_.subscribe(self, classOf[MemberEvent], classOf[ReachabilityEvent]))
    }

    // all members of the cluster that are available
    var availableMembers = Set.empty[Member]

    override def receive: Receive = {
      case CurrentInvokerPoolState(newState) =>
        schedulingState.updateInvokers(newState)

      // State of the cluster as it is right now
      case CurrentClusterState(members, _, _, _, _) =>
        availableMembers = members.filter(_.status == MemberStatus.Up)
        schedulingState.updateCluster(availableMembers.size)

      // General lifecycle events and events concerning the reachability of members. Split-brain is not a huge concern
      // in this case as only the invoker-threshold is adjusted according to the perceived cluster-size.
      // Taking the unreachable member out of the cluster from that point-of-view results in a better experience
      // even under split-brain-conditions, as that (in the worst-case) results in premature overloading of invokers vs.
      // going into overflow mode prematurely.
      case event: ClusterDomainEvent =>
        availableMembers = event match {
          case MemberUp(member)          => availableMembers + member
          case ReachableMember(member)   => availableMembers + member
          case MemberRemoved(member, _)  => availableMembers - member
          case UnreachableMember(member) => availableMembers - member
          case _                         => availableMembers
        }

        schedulingState.updateCluster(availableMembers.size)
    }
  }))

  /** Loadbalancer interface methods */
  override def invokerHealth(): Future[IndexedSeq[InvokerHealth]] = Future.successful(schedulingState.invokers)
  override def clusterSize: Int = schedulingState.invokers.length

  /** 1. Publish a message to the loadbalancer */
  override def publish(action: ExecutableWhiskActionMetaData, msg: ActivationMessage)(
    implicit transid: TransactionId): Future[Future[Either[ActivationId, WhiskActivation]]] = {

      val chosen = ConsistentCacheLoadBalancer.schedule(action.fullyQualifiedName(true),
                                                        schedulingState, 
                                                        msg.activationId, 
                                                        lbConfig.loadStrategy,
                                                        lbConfig.algorithm)

    chosen.map { invoker => 
      // MemoryLimit() and TimeLimit() return singletons - they should be fast enough to be used here
      val memoryLimit = action.limits.memory
      val memoryLimitInfo = if (memoryLimit == MemoryLimit()) { "std" } else { "non-std" }
      val timeLimit = action.limits.timeout
      val timeLimitInfo = if (timeLimit == TimeLimit()) { "std" } else { "non-std" }
      logging.info(this,
        s"scheduled activation ${msg.activationId}, action '${msg.action.asString}', ns '${msg.user.namespace.name.asString}', mem limit ${memoryLimit.megabytes} MB (${memoryLimitInfo}), time limit ${timeLimit.duration.toMillis} ms (${timeLimitInfo}) to ${invoker}")
      val activationResult = setupActivation(msg, action, invoker)
      sendActivationToInvoker(messageProducer, msg, invoker).map(_ => activationResult)
    }
    .getOrElse {
      // report the state of all invokers
      val invokerStates = schedulingState.invokers.foldLeft(Map.empty[InvokerState, Int]) { (agg, curr) =>
        val count = agg.getOrElse(curr.status, 0) + 1
        agg + (curr.status -> count)
      }

      logging.error(
        this,
        s"failed to schedule activation ${msg.activationId}, action '${msg.action.asString}', ns '${msg.user.namespace.name.asString}' - invokers to use: $invokerStates")
      Future.failed(LoadBalancerException("No invokers available"))
    }
  }

  override val invokerPool =
    invokerPoolFactory.createInvokerPool(
      actorSystem,
      messagingProvider,
      messageProducer,
      sendActivationToInvoker,
      Some(monitor))

  override def releaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry) = {
      schedulingState.stateReleaseInvoker(invoker, entry)
  }

  override def updateActionTimes() = {
    try {
      // logging.info(this, s"Connecting to Redis")
      // val r = new Jedis("lbConfig.redis.ip", 1111)
      val r = new Jedis(lbConfig.redis.ip, lbConfig.redis.port)
      r.auth(lbConfig.redis.password)
      
      for (invoker <- schedulingState.invokers)
      {
        val id = invoker.id.instance
        val packetStr = Option(r.get(s"$id/packet"))
        
        packetStr match {
          case Some(realStr) => {
            val packet = realStr.parseJson.convertTo[RedisPacket]

            schedulingState.updateCPUUsage(invoker.id, packet.cpuLoad, packet.running, packet.runningAndQ, packet.loadAvg)
            schedulingState.updateMemUsage(invoker.id, packet.containerActiveMem, packet.usedMem)
            schedulingState.updateRuntimeData(packet.priorities)
          }
          case None =>  logging.warn(this, s"Could not get redis packet for invoker $id")
        }
      }
    } catch {
        case e: redis.clients.jedis.exceptions.JedisDataException => logging.warn(this, s"Failed to log into redis server, $e")
        case scala.util.control.NonFatal(t) => {
          var trace = t.getStackTrace.map { trace => trace.toString() }.mkString("\n")
          logging.error(this, s"Unknonwn error, '$t', at ${trace}")
        } 
    }
    schedulingState.emitMetrics()
  }  
}

object ConsistentCacheLoadBalancer extends LoadBalancerProvider {

  override def instance(whiskConfig: WhiskConfig, instance: ControllerInstanceId)(
    implicit actorSystem: ActorSystem,
    logging: Logging): LoadBalancer = {

    val invokerPoolFactory = new InvokerPoolFactory {
      override def createInvokerPool(
        actorRefFactory: ActorRefFactory,
        messagingProvider: MessagingProvider,
        messagingProducer: MessageProducer,
        sendActivationToInvoker: (MessageProducer, ActivationMessage, InvokerInstanceId) => Future[RecordMetadata],
        monitor: Option[ActorRef]): ActorRef = {

        InvokerPool.prepare(instance, WhiskEntityStore.datastore())

        actorRefFactory.actorOf(
          InvokerPool.props(
            (f, i) => f.actorOf(InvokerActor.props(i, instance)),
            (m, i) => sendActivationToInvoker(messagingProducer, m, i),
            messagingProvider.getConsumer(whiskConfig, s"health${instance.asString}", "health", maxPeek = 128),
            monitor))
      }

    }
    new ConsistentCacheLoadBalancer(
      whiskConfig,
      instance,
      createFeedFactory(whiskConfig, instance),
      invokerPoolFactory)
  }

  def requiredProperties: Map[String, String] = kafkaHosts

  /**
   * Scans through all invokers and searches for an invoker tries to get a free slot on an invoker. 
   *
   * @param fqn action name to be scheduled
   * @return an invoker to schedule to
   */
  def schedule(
    fqn: FullyQualifiedEntityName,
    state: ConsistentCacheLoadBalancerState,
    activationId: ActivationId,
    loadStrategy: String,
    algo: String)(implicit logging: Logging, transId: TransactionId): Option[InvokerInstanceId] = {
      logging.info(this, s"Scheduling action '${fqn}' with TransactionId ${transId}")
      algo match {
        case "ConsistentCache" => state.getInvokerConsistentCache(fqn, activationId, loadStrategy)
        case "BoundedLoad" => state.getInvokerBoundedLoad(fqn, activationId, loadStrategy)
        case "ConsistentHash" => state.getInvokerConsistentHash(fqn, activationId, loadStrategy)
        case "RoundRobin" => state.roundRobin()
        case _ => {
          logging.error(this, s"schedule: Unsupported loadbalancing algorithm ${algo}")
          None
        }
      }  
    }
}

class ConsisntentCacheInvokerNode(_invoker: InvokerInstanceId, _load: Option[AtomicInteger])(implicit logging: Logging)
  extends Node {
  
  val invoker : InvokerInstanceId = _invoker
  logging.info(this,
        s"ConsisntentCacheInvokerNode created for invoker '${_invoker}' with passed load of '${_load}'")

  var load : AtomicInteger = _load.getOrElse(new AtomicInteger(0))

  override def getKey() : String = {
    invoker.toString
  }
}

/**
 * Holds the state necessary for scheduling of actions.
 *
 * @param _invokers all of the known invokers in the system
 */
case class ConsistentCacheLoadBalancerState(
  private var _consistentHash: ConsistentHash[ConsisntentCacheInvokerNode] = HashRing.newBuilder().build(),
  private var _consistentHashList: List[ConsisntentCacheInvokerNode] = List(),

  // private var startTimes: mutable.Map[ActivationId, Long] = mutable.Map.empty[ActivationId, Long],
  private var runTimes: mutable.Map[String, (Double, Double)] = mutable.Map.empty[String, (Double, Double)], // (warm, cold)
  private var cpuLoad: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  private var runningLoad: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  private var runningAndQLoad: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  private var memLoad: mutable.Map[InvokerInstanceId, (Double, Double)] = mutable.Map.empty[InvokerInstanceId, (Double, Double)], // (used, active-used)
  private var minuteLoadAvg: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  private var robinInt: Int = 0,

  private var _invokers: IndexedSeq[InvokerHealth] = IndexedSeq.empty[InvokerHealth])(
  lbConfig: ShardingContainerPoolBalancerConfig =
    loadConfigOrThrow[ShardingContainerPoolBalancerConfig](ConfigKeys.loadbalancer))(implicit logging: Logging) {

  /** Getters for the variables, setting from the outside is only allowed through the update methods below */
  def invokers: IndexedSeq[InvokerHealth] = _invokers

  def updateCPUUsage(invoker: InvokerInstanceId, load: Double, running: Double, runningAndQ: Double, loadAvg: Double) : Unit = {
    cpuLoad += (invoker -> load)
    runningLoad += (invoker -> running)
    runningAndQLoad += (invoker -> runningAndQ)
    minuteLoadAvg += (invoker -> loadAvg)
  }

  def updateMemUsage(invoker: InvokerInstanceId, activeMem: Double, usedMem: Double) : Unit = {
    memLoad += (invoker -> (usedMem, activeMem))
  }

  def emitMetrics() : Unit = {
    logging.info(this, s"Current system data= runtimes: $runTimes, cpu load: $cpuLoad, mem load: $memLoad, running load: $runningLoad, minute Load Avg: $minuteLoadAvg")
  }

  def updateRuntimeData(data: List[(String,Double,Double)]) : Unit = {
    for (packet <- data)
    {
      val current_data = runTimes.getOrElse(packet._1, (0.0, 0.0))
      var warmTime = current_data._1
      if (warmTime == 0){
        warmTime = packet._2
      }
      var coldTime = current_data._2
      if (coldTime == 0){
        coldTime = packet._3
      }
      if (packet._2 > 0)
      {
        warmTime = current_data._1 * 0.9 + (0.1 * packet._2)
      }
      if (packet._3 > 0)
      {
        coldTime = current_data._2 * 0.9 + (0.1 * packet._3)
      }
      runTimes += (packet._1 -> (warmTime, coldTime) )
    }
  }

  private def updateTrackingData(node: ConsisntentCacheInvokerNode, activationId: ActivationId) : Option[InvokerInstanceId] = {
    node.load.incrementAndGet()
    return Some(node.invoker)
  }

  private def getLoad(node: ConsisntentCacheInvokerNode, loadStrategy: String) : Double = {
    loadStrategy match {
      case "SimpleLoad" => node.load.doubleValue() / lbConfig.invoker.cores
      case "Running" => runningLoad.getOrElse(node.invoker, 0.0)
      case "RAndQ" => runningAndQLoad.getOrElse(node.invoker, 0.0)
      case "CPU" => cpuLoad.getOrElse(node.invoker, 0.0)
      case "UsedMem" => memLoad.getOrElse(node.invoker, (0.0, 0.0))._1
      case "ActiveMem" => memLoad.getOrElse(node.invoker, (0.0, 0.0))._2
      case "LoadAvg" => minuteLoadAvg.getOrElse(node.invoker, 0.0)  / lbConfig.invoker.cores
      case _ => {
        logging.error(this, s"getLoad: Unsupported loadbalancing strat ${loadStrategy}")
        2.0
      }
    }
  }

  private def getLoadCutoff(loadStrategy: String) : Double = {
    loadStrategy match {
      case "SimpleLoad" => lbConfig.invoker.boundedCeil * lbConfig.invoker.c
      case "Running" => lbConfig.invoker.boundedCeil * lbConfig.invoker.c
      case "RAndQ" => lbConfig.invoker.boundedCeil * lbConfig.invoker.c
      case "CPU" => lbConfig.invoker.c
      case "UsedMem" => lbConfig.invoker.c
      case "ActiveMem" => lbConfig.invoker.c
      case "LoadAvg" => lbConfig.invoker.boundedCeil * lbConfig.invoker.c
      case _ => {
        logging.error(this, s"getLoadCutoff: Unsupported loadbalancing strat ${loadStrategy}")
        2.0
      }
    }
  }

  def roundRobin() : Option[InvokerInstanceId] = {
    val ret = _invokers(robinInt)
    robinInt += 1
    robinInt %= _invokers.length;
    return Some(ret.id)
  }

  def getInvokerConsistentHash(fqn: FullyQualifiedEntityName, activationId: ActivationId, loadStrategy: String) : Option[InvokerInstanceId] = {
    val strName = s"${fqn.namespace}/${fqn.name}"
    val possNode = _consistentHash.locate(strName)
    if (possNode.isPresent)
    {
      Some(possNode.get().invoker)
    }
    else None
  }

  def getInvokerBoundedLoad(fqn: FullyQualifiedEntityName, activationId: ActivationId, loadStrategy: String) : Option[InvokerInstanceId] = {
    val strName = s"${fqn.namespace}/${fqn.name}"
    val possNode = _consistentHash.locate(strName)
    if (possNode.isPresent)
    {
      val loadCuttoff = getLoadCutoff(loadStrategy)
      var node = possNode.get()
      val orig_invoker = node.invoker
      val idx = _consistentHashList.indexWhere( p => p.invoker == orig_invoker)
      val cutoff = min(_invokers.length, loadCuttoff).toInt

      for (i <- 0 to cutoff) {
        val id = (idx + i) % _invokers.length
        node = _consistentHashList(id)
        val serverLoad = getLoad(node, loadStrategy)

        if (serverLoad <= loadCuttoff) {
          logging.info(this, s"Invoker ${orig_invoker} overloaded, assigning work to node under cutoff ${node.invoker}")
          /* assign load to node */
          return updateTrackingData(node, activationId)
        }
      }
      /* went around enough, give up */
      return updateTrackingData(node, activationId)
    }
     else None
  }

  def getInvokerConsistentCache(fqn: FullyQualifiedEntityName, activationId: ActivationId, loadStrategy: String) : Option[InvokerInstanceId] = {
    val strName = s"${fqn.namespace}/${fqn.name}"
    val possNode = _consistentHash.locate(strName)
    if (possNode.isPresent)
    {
      var original_node = possNode.get()
      val orig_serverLoad = getLoad(original_node, loadStrategy)
      var node = original_node
      val loadCuttoff = getLoadCutoff(loadStrategy)

      val idx = _consistentHashList.indexWhere( p => p.invoker == original_node.invoker)
      val chainLen = _invokers.length // min(_invokers.length, loadCuttoff).toInt
      var times = runTimes.getOrElse(strName, (0.0, 0.0))
      var r: Double = 2.2
      if (times._1 != 0.0) {
        r = times._2 / times._1
        r = min(r, 2.2)
      }

      for (i <- 0 to chainLen) {
        var id = (idx + i) % _invokers.length
        node = _consistentHashList(id)
        val serverLoad = getLoad(node, loadStrategy)

        if (serverLoad <= loadCuttoff) {
          // logging.info(this, s"Invoker ${original_node.invoker} overloaded with $orig_serverLoad, assigning work to node under cutoff ${node.invoker}")
          /* assign load to node */
          return updateTrackingData(node, activationId)
        }
        else if (serverLoad <= r-1) {
          // logging.info(this, s"Invoker ${original_node.invoker} overloaded with $orig_serverLoad, assigning work to node with load under $r - 1 ${node.invoker}")
          return updateTrackingData(node, activationId)
        }
      }
      /* went around enough, give up */
      return updateTrackingData(node, activationId)
    }
     else None
  }

  /**
   * Updates the scheduling state with the new invokers.
   *
   * This is okay to not happen atomically since dirty reads of the values set are not dangerous. It is important though
   * to update the "invokers" variables last, since they will determine the range of invokers to choose from.
   */
  def updateInvokers(newInvokers: IndexedSeq[InvokerHealth]): Unit = {
    val oldSize = _invokers.size
    val newSize = newInvokers.size

    val newHash : ConsistentHash[ConsisntentCacheInvokerNode] = HashRing.newBuilder().build()
    newInvokers.map { invoker => 
      
      val currentLoad: Option[AtomicInteger] = _consistentHashList.find(p => p.invoker == invoker.id).map { _.load }
      newHash.add(new ConsisntentCacheInvokerNode(invoker.id, currentLoad))
    
    } // .toString()

    _invokers = newInvokers
    _consistentHash = newHash
    _consistentHashList = List() ++ _consistentHash.getNodes().iterator().asScala

    logging.info(this,
      s"loadbalancer invoker status updated. num invokers = ${newSize}, length of _consistentHashList = ${_consistentHashList.size}, invokerCores = ${lbConfig.invoker.cores} c = ${lbConfig.invoker.c}")(
      TransactionId.loadbalancer)
  }

  def stateReleaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry): Unit = {
    val found = _consistentHashList.find(node => node.invoker == invoker)
    found.map { invok =>
      invok.load.decrementAndGet()
      logging.info(
        this,
        s"Activation ${entry} released on invoker ${invoker}, current load: ${invok.load}")
    }.getOrElse {
      logging.error(
        this,
        s"Tried to release activation '${entry}'' on invoker that doesn't exist '${invoker}'")
    }
  }

  def updateCluster(newSize: Int): Unit = {
    // do nothing?
  }
}
