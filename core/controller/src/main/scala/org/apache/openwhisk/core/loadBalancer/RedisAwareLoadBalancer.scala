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

// import akka.actor.ActorRef
// import akka.actor.ActorRefFactory

import akka.actor.{Actor, ActorSystem, Props}
import akka.cluster.ClusterEvent._
import akka.cluster.{Cluster, Member, MemberStatus}
import akka.management.scaladsl.AkkaManagement
import akka.management.cluster.bootstrap.ClusterBootstrap
// import akka.stream.ActorMaterializer
// import org.apache.kafka.clients.producer.RecordMetadata
import pureconfig._
import pureconfig.generic.auto._
import org.apache.openwhisk.common._
// import org.apache.openwhisk.core.WhiskConfig._
import org.apache.openwhisk.core.connector._
import org.apache.openwhisk.core.entity._
import org.apache.openwhisk.common.LoggingMarkers._
// import org.apache.openwhisk.core.loadBalancer.InvokerState.{Healthy, Offline, Unhealthy, Unresponsive}
import org.apache.openwhisk.core.{ConfigKeys, WhiskConfig}
import org.apache.openwhisk.spi.SpiLoader

import scala.concurrent.Future
import scala.collection.JavaConverters._
import java.util.concurrent.atomic.AtomicInteger
// import scala.math.{min} //, max}
import scala.collection.mutable

import org.ishugaliy.allgood.consistent.hash.{HashRing, ConsistentHash}
import org.ishugaliy.allgood.consistent.hash.node.{Node}
import redis.clients.jedis.{Jedis}
import spray.json._
import org.apache.openwhisk.common.RedisPacketProtocol._

/**
 * A loadbalancer that schedules workload based on 
 */
abstract class RedisAwareLoadBalancer(
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
  protected val schedulingState = RedisAwareLoadBalancerState()(lbConfig)

  /**
   * Monitors invoker supervision and the cluster to update the state sequentially
   *
   * All state updates should go through this actor to guarantee that
   * [[RedisAwareLoadBalancerState.updateInvokers]] and [[RedisAwareLoadBalancerState.updateCluster]]
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

  override protected def updateActionTimes() = {
    try {
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
          logging.error(this, s"Unknonwn error updating from Redis, '$t', at ${trace}")
        } 
    }
    schedulingState.emitMetrics()
  }  
}

class ConsistentCacheInvokerNode(_invoker: InvokerInstanceId, _load: Option[AtomicInteger])(implicit logging: Logging)
  extends Node {
  
  val invoker : InvokerInstanceId = _invoker
  logging.info(this,
        s"ConsistentCacheInvokerNode created for invoker '${_invoker}' with passed load of '${_load}'")

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
case class RedisAwareLoadBalancerState(
  var _consistentHash: ConsistentHash[ConsistentCacheInvokerNode] = HashRing.newBuilder().build(),
  var _consistentHashList: List[ConsistentCacheInvokerNode] = List(),

  // private var startTimes: mutable.Map[ActivationId, Long] = mutable.Map.empty[ActivationId, Long],
  var runTimes: mutable.Map[String, (Double, Double)] = mutable.Map.empty[String, (Double, Double)], // (warm, cold)
  var cpuLoad: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  var runningLoad: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  var runningAndQLoad: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  var memLoad: mutable.Map[InvokerInstanceId, (Double, Double)] = mutable.Map.empty[InvokerInstanceId, (Double, Double)], // (used, active-used)
  var minuteLoadAvg: mutable.Map[InvokerInstanceId, Double] = mutable.Map.empty[InvokerInstanceId, Double],
  private var nodeMap: mutable.Map[String, ConsistentCacheInvokerNode] = mutable.Map.empty[String, ConsistentCacheInvokerNode],

  private var _invokers: IndexedSeq[InvokerHealth] = IndexedSeq.empty[InvokerHealth])(
  lbConfig: ShardingContainerPoolBalancerConfig =
    loadConfigOrThrow[ShardingContainerPoolBalancerConfig](ConfigKeys.loadbalancer))(implicit logging: Logging) {

  /** Getters for the variables, setting from the outside is only allowed through the update methods below */
  def invokers: IndexedSeq[InvokerHealth] = _invokers

  def locateNode(name: String) : Option[ConsistentCacheInvokerNode] = {
    val found = nodeMap get name
    found match {
      case Some(_) => found
      case None => {
        val hashedNode = _consistentHash.locate(name)
        if (hashedNode.isPresent) {
          val node = hashedNode.get()
          nodeMap += (name -> node)
          Some(node)
        } else {
          logging.error(this, s"Unable to locate hashed node for name $name")
          None
        }
      }
    }
  }

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

  def updateTrackingData(node: ConsistentCacheInvokerNode, loadStrategy: String) : Unit = {
      loadStrategy match {
        case "SimpleLoad" => node.load.incrementAndGet()
        case _ => None
      }
  }

  def getLoad(node: ConsistentCacheInvokerNode, loadStrategy: String) : Double = {
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

  def getLoadCutoff(loadStrategy: String) : Double = {
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

  /**
   * Updates the scheduling state with the new invokers.
   *
   * This is okay to not happen atomically since dirty reads of the values set are not dangerous. It is important though
   * to update the "invokers" variables last, since they will determine the range of invokers to choose from.
   */
  def updateInvokers(newInvokers: IndexedSeq[InvokerHealth]): Unit = {
    val oldSize = _invokers.size
    val newSize = newInvokers.size

    val newHash : ConsistentHash[ConsistentCacheInvokerNode] = HashRing.newBuilder().build()
    newInvokers.map { invoker => 
      
      val currentLoad: Option[AtomicInteger] = _consistentHashList.find(p => p.invoker == invoker.id).map { _.load }
      if (invoker.status.isUsable) {
        newHash.add(new ConsistentCacheInvokerNode(invoker.id, currentLoad))
      }
      else {
        logging.warn(this,
          s"not adding unusable invoker to consistent hash: $invoker")(
          TransactionId.loadbalancer)        
      }
    
    } // .toString()

    _invokers = newInvokers
    _consistentHash = newHash
    _consistentHashList = List() ++ _consistentHash.getNodes().iterator().asScala
    nodeMap = mutable.Map.empty[String, ConsistentCacheInvokerNode]

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
