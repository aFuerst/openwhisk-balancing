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
import java.time.Instant

import org.ishugaliy.allgood.consistent.hash.{HashRing, ConsistentHash}
import org.ishugaliy.allgood.consistent.hash.node.{Node}
import redis.clients.jedis.{Jedis}
import spray.json._
import DefaultJsonProtocol._

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

  override protected def emitMetrics() = {
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

      val chosen = ConsistentCacheLoadBalancer.schedule(action.fullyQualifiedName(true), schedulingState, msg.activationId)

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

  override protected def releaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry) = {
      schedulingState.stateReleaseInvoker(invoker, entry)
  }

  override protected def updateActionTimes() = {
    try {
      logging.info(this, s"Connecting to Redis")
      val r = new Jedis("172.17.0.1", 6379)
      r.auth("openwhisk")
      
      for (invoker <- schedulingState.invokers)
      {
        val id = invoker.id.instance
        val data = r.get(s"$id/warm-cold-data")
        logging.info(this, s"Got json from Redis, invoker: $id, warm:${data}")
        val parsedData = data.parseJson.convertTo[List[(String,Long,Long)]]
        schedulingState.updateRuntimeData(parsedData)
      }
    } catch {
        case e: redis.clients.jedis.exceptions.JedisDataException => logging.error(this, s"Failed to log into redis server, $e")
        case scala.util.control.NonFatal(t) => logging.error(this, s"Unkonwn error, $t")
    }
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
    activationId: ActivationId)(implicit logging: Logging, transId: TransactionId): Option[InvokerInstanceId] = {
      logging.info(this, s"Scheduling action '${fqn}' with TransactionId ${transId}")
      state.getInvoker(fqn, activationId)
  }
}

class ConsisntentCacheInvokerNode(_invoker: InvokerInstanceId)
  extends Node {
  
  val invoker : InvokerInstanceId = _invoker
  var load : AtomicInteger = new AtomicInteger(0)

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
  private var runTimes: mutable.Map[String, (Long, Long)] = mutable.Map.empty[String, (Long, Long)], // (warm, cold)

  private var _invokers: IndexedSeq[InvokerHealth] = IndexedSeq.empty[InvokerHealth])(
  lbConfig: ShardingContainerPoolBalancerConfig =
    loadConfigOrThrow[ShardingContainerPoolBalancerConfig](ConfigKeys.loadbalancer))(implicit logging: Logging) {

  /** Getters for the variables, setting from the outside is only allowed through the update methods below */
  def invokers: IndexedSeq[InvokerHealth] = _invokers

  private def getMilis(): Long = {
    Instant.now().toEpochMilli()
  }

  def updateRuntimeData(data: List[(String,Long,Long)]) : Unit = {
    for (packet <- data)
    {
      runTimes += (packet._1 -> (packet._2, packet._3))
    }
  }

  private def updateTrackingData(node: ConsisntentCacheInvokerNode, activationId: ActivationId) : Option[InvokerInstanceId] = {
    node.load.incrementAndGet()
    // startTimes += (activationId -> getMilis())
    return Some(node.invoker)
  }

  def getInvoker(fqn: FullyQualifiedEntityName, activationId: ActivationId) : Option[InvokerInstanceId] = {
    val strName = s"${fqn.namespace}/${fqn.name}"
    val possNode = _consistentHash.locate(strName)
    if (possNode.isPresent)
    {
      var node = possNode.get()
      val serverLoad = node.load.doubleValue()
      val loadCuttoff = lbConfig.invoker.cores * lbConfig.invoker.c
      if (serverLoad <= loadCuttoff)
      {
        /* assign load to node */
        return updateTrackingData(node, activationId)
      }

      val idx = _consistentHashList.indexWhere( p => p.invoker == node.invoker)
      val cutoff = min(_invokers.length, loadCuttoff).toInt

      for (i <- 0 to cutoff)
      {
        var id = (cutoff + i) % _invokers.length
        node = _consistentHashList(id)

        if (serverLoad <= loadCuttoff)
        {
          /* assign load to node */
          return updateTrackingData(node, activationId)
        }
        else 
        {
          var times = runTimes.getOrElse(strName, (0L, 0L))
          var r: Double = 0
          if (times._2 != 0)
          {
            r = times._2 / times._1
          }
          if (loadCuttoff <= r-1)
          {
            return updateTrackingData(node, activationId)
          }
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
    newInvokers.map {invoker => newHash.add(new ConsisntentCacheInvokerNode(invoker.id))} // .toString()

    _invokers = newInvokers
    _consistentHash = newHash
    _consistentHashList = List() ++ _consistentHash.getNodes().iterator().asScala

    logging.info(this,
      s"loadbalancer invoker status updated. num invokers = $newSize, invokerCores = ${lbConfig.invoker.cores} c = ${lbConfig.invoker.c}")(
      TransactionId.loadbalancer)
  }

  def stateReleaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry): Unit = {
    val found = _consistentHashList.find(node => node.invoker == invoker)
    found.map { invok =>
      invok.load.decrementAndGet()

      // val found = startTimes get entry.id
      // var times = runTimes.getOrElse(entry.fullyQualifiedEntityName, (1000000000000L, 0L))

      // found match {
      //   case Some(startTime) => {
      //     val elapsed = getMilis() - startTime
      //     val warm = min(times._1, elapsed)
      //     val cold = max(times._2, elapsed)
      //     runTimes += (entry.fullyQualifiedEntityName -> (warm, cold))
      //     logging.info(
      //       this,
      //       s"Updated times for ${entry.fullyQualifiedEntityName} to ${(warm, cold)}")
      //   }
      //   case None => logging.error(this, s"Unexpected data invoker '${invoker}' with entry '${entry}'")
      // }

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
