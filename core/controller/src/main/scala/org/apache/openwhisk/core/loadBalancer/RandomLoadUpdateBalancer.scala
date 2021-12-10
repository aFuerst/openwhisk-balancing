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

import akka.actor.{ActorSystem}
import org.apache.kafka.clients.producer.RecordMetadata
import org.apache.openwhisk.common._
import org.apache.openwhisk.core.WhiskConfig._
import org.apache.openwhisk.core.connector._
import org.apache.openwhisk.core.entity._
import org.apache.openwhisk.core.{WhiskConfig}
import org.apache.openwhisk.spi.SpiLoader

import scala.concurrent.Future
import scala.math.{min}
import org.apache.commons.math3.distribution.{NormalDistribution}
import org.apache.commons.math3.stat.descriptive.rank.Percentile
import scala.collection.mutable
import org.apache.openwhisk.core.{WhiskConfig}
// import pureconfig._
// import pureconfig.generic.auto._
import scala.util.Random
import java.time.Instant
import scala.collection.concurrent.TrieMap

/**
 * A loadbalancer that schedules workload based on random-forwarding consistent hashing load balancer
 */
class RandomLoadUpdateBalancer(
  config: WhiskConfig,
  controllerInstance: ControllerInstanceId,
  feedFactory: FeedFactory,
  invokerPoolFactory: InvokerPoolFactory,
  messagingProvider: MessagingProvider = SpiLoader.get[MessagingProvider])(
  implicit actorSystem: ActorSystem,
  logging: Logging)
    extends RedisAwareLoadBalancer(config, controllerInstance, feedFactory, invokerPoolFactory) {


  /** 1. Publish a message to the loadbalancer */
  override def publish(action: ExecutableWhiskActionMetaData, msg: ActivationMessage)(
    implicit transid: TransactionId) : Future[Future[Either[ActivationId, WhiskActivation]]] = {

      val chosen = RandomLoadUpdateBalancer.schedule(action.fullyQualifiedName(true),
                                                        schedulingState, 
                                                        msg.activationId, 
                                                        lbConfig)

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

  override protected def customUpdate() : Unit = {
    RandomLoadUpdateBalancer.updatePopularity(schedulingState)
  }
}

object RandomLoadUpdateBalancer extends LoadBalancerProvider {

  // private var popularity: mutable.Map[String, Long] = mutable.Map[String, Long]().withDefaultValue(0)
  private var popular: mutable.Map[String, Boolean] = mutable.Map[String, Boolean]().withDefaultValue(false)
  private val last_access_times : TrieMap[String, Long] = TrieMap.empty[String, Long]
  private val inter_arival_times : TrieMap[String, Double] = TrieMap.empty[String, Double]
  private val percentile_popular : Double = 20.0
  private var popular_threshold : Double = 0.0
  private var avg_arrival_rate : Double = 0.0
  private var ema_alph : Double = 0.9

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
    new RandomLoadUpdateBalancer(
      whiskConfig,
      instance,
      createFeedFactory(whiskConfig, instance),
      invokerPoolFactory)
  }

  def updatePopularity(schedulingState: RedisAwareLoadBalancerState)(implicit logging: Logging) : Unit = {
    logging.info(this, s"calculating popularity")(TransactionId.invokerRedis)
    val p = new Percentile()
    val list = inter_arival_times.values.toArray.sorted
    popular_threshold =  p.evaluate(list, percentile_popular) // percentile(list, percentile_popular)
    val avg_iat = p.evaluate(list, 50.0)
    avg_arrival_rate = 1.0 / (avg_iat/1000.0)
    logging.info(this, s"calculated popularity; avg_iat = ${avg_iat}; avg_arrival_rate = ${avg_arrival_rate}; popular_threshold=${popular_threshold}; iats = ${inter_arival_times}")(TransactionId.invokerRedis)

    var state = inter_arival_times.keys.iterator.foldLeft("") { (agg, curr) =>
      val iat = inter_arival_times(curr)
      val pop = iat <= popular_threshold
      popular += (curr -> pop)
      agg + s"${curr} has IAT of ${iat} and is popular? ${pop}; "
    }
    logging.info(this, state)(TransactionId.invokerRedis)
  }

  def now() : Long = {
    Instant.now().toEpochMilli()
  }

  def updateShardsPopular(actionName: String)(implicit logging: Logging, transid: TransactionId) : Unit = {
    val P = 100.0
    val T = 100.0 // 20.0
    val r_orig = T/P // Effective sampling rate 
    val Ti = actionName.hashCode().abs % P
    if (Ti < T) {
      val found = last_access_times get actionName
      found match {
        case Some(last_access_time) => {
          val curr_t = now()
          val iat = (curr_t - last_access_time) / r_orig
          var ema_iat = inter_arival_times.getOrElse(actionName, iat)
          ema_iat = (iat * ema_alph) + ((1-ema_alph) * ema_iat)
          last_access_times += (actionName -> curr_t)
          inter_arival_times += (actionName -> ema_iat)
          // logging.info(this, s"updating SHARDS popularity IAT for function ${actionName}, new IAT is ${ema_iat}")(transid)

        }
        case None => {
          val curr_t = now()
          last_access_times += (actionName -> curr_t)
          // inter_arival_times += (actionName -> curr_t / r_orig)
        }
      }
    }
  }

  def noisyLoad(load: Double, schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig)(implicit logging: Logging, transid: TransactionId) : Double = {
    if (popular_threshold == 0) {
      return load
    }

    val s = 1
    val server_arrival_rate = avg_arrival_rate  / schedulingState._consistentHashList.length
    val extra_anticip_load = server_arrival_rate / lbConfig.invoker.cores * s 
    // val distrib = new NormalDistribution(server_arrival_rate*lbConfig.invoker.boundedCeil, 0.1*lbConfig.invoker.boundedCeil)
    val distrib = new NormalDistribution(extra_anticip_load, 0.1)
    return load + distrib.sample()
  }

  def runLocalCondition(node: ConsistentCacheInvokerNode, actionName: String, schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig)(implicit logging: Logging, transid: TransactionId) : Boolean = {
    // assume function is popular
    val load = schedulingState.getLoad(node, lbConfig.loadStrategy)
    val Lnoisy = load +  noisyLoad(load, schedulingState, lbConfig)
    Lnoisy <= lbConfig.invoker.boundedCeil
  }

  def requiredProperties: Map[String, String] = kafkaHosts

  def isPopular(schedulingState: RedisAwareLoadBalancerState,name: String)(implicit logging: Logging, transid: TransactionId) : Boolean = {
    return popular(name)
  }

  /**
   * Scans through all invokers and searches for an invoker tries to get a free slot on an invoker. 
   *
   * @param fqn action name to be scheduled
   * @return an invoker to schedule to
   */
  def schedule(
    fqn: FullyQualifiedEntityName,
    schedulingState: RedisAwareLoadBalancerState,
    activationId: ActivationId,
    lbConfig: ShardingContainerPoolBalancerConfig)
    (implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem) : Option[InvokerInstanceId] = {   
    // logging.info(this, s"Scheduling action '${fqn}' with TransactionId ${transId}")(transId)
    
    val strName = s"${fqn.namespace}/${fqn.name}"
    updateShardsPopular(strName)
    // val func_pop = popularity(strName) + 1//.increment()
    // popularity += (strName -> func_pop)
    if (! isPopular(schedulingState, strName)) {
      // logging.info(this, s"unpopular function ${strName} :(")(transId)
      return getInvokerConsistentCache(fqn, schedulingState, activationId, lbConfig)
    }
    // logging.info(this, s"Popular function ${strName}!")(transId)

    val possNode = schedulingState.locateNode(strName)
    var chain_len = 0
    possNode match {
      case Some (foundNode) => {
        var node = foundNode
        val orig_invoker = node.invoker
        val idx = schedulingState._consistentHashList.indexWhere( p => p.invoker == orig_invoker)

        // hash list has one node per healthy invoker
        val max_chain = schedulingState._consistentHashList.length

        for (i <- 0 to max_chain) {
          val id = (idx + i) % schedulingState._consistentHashList.length
          node = schedulingState._consistentHashList(id)

          if (runLocalCondition(node, strName, schedulingState, lbConfig)) {
            if (chain_len > 0) {
              logging.info(this, s"Activation ${activationId} was pushed ${chain_len} places to ${node.invoker}, from ${orig_invoker}")(transId)
            }

            schedulingState.updateTrackingData(node, lbConfig.loadStrategy)
            return Some(node.invoker)
          }

          // logging.info(this, s"forwarding from invoker ${node.invoker}, load: ${serverLoad}")(transId)
          chain_len += 1
        }
        /* went around enough, give up */
        node = schedulingState._consistentHashList(Random.nextInt(schedulingState._consistentHashList.size))
        if (chain_len > 0) {
          logging.info(this, s"Activation ${activationId} was pushed full circle ${chain_len} places; randomly sending to ${node.invoker}, from ${orig_invoker}")(transId)
          schedulingState.wakeUpInvoker()
        }
        schedulingState.updateTrackingData(node, lbConfig.loadStrategy)
        return Some(node.invoker)
      }
      case None => None
    }
  }

  def getInvokerConsistentCache(
    fqn: FullyQualifiedEntityName, 
    schedulingState: RedisAwareLoadBalancerState, 
    activationId: ActivationId, 
    lbConfig: ShardingContainerPoolBalancerConfig)(implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem) : Option[InvokerInstanceId] = {
       
    val strName = s"${fqn.namespace}/${fqn.name}"
    var times = schedulingState.runTimes.getOrElse(strName, (0.0, 0.0))
    var r_orig: Double = 2.2
    var slowdown = 1.2*(lbConfig.invoker.boundedCeil+1)
    if (times._1 != 0.0) {
      r_orig = times._2 / times._1
      slowdown = min(r_orig, slowdown)
    }
    val thresh = slowdown-1.0

    val possNode = schedulingState.locateNode(strName)
    possNode match {
      case Some (foundNode) => {
        var original_node = foundNode
        val orig_serverLoad = schedulingState.getLoad(original_node, lbConfig.loadStrategy)
        var node = original_node
        val loadCuttoff = schedulingState.getLoadCutoff(lbConfig.loadStrategy)

        val idx = schedulingState._consistentHashList.indexWhere( p => p.invoker == original_node.invoker)
        val max_chain = schedulingState._consistentHashList.length


        for (i <- 0 to max_chain) {
          var id = (idx + i) % schedulingState._consistentHashList.length
          node = schedulingState._consistentHashList(id)
          val serverLoad = schedulingState.getLoad(node, lbConfig.loadStrategy)

          if (serverLoad - thresh <= 0) {
            if (i > 0) {
              logging.info(this, s"unpopular Activation ${activationId} was pushed ${i} places to ${node.invoker}, from ${original_node.invoker}")(transId)
            }
            /* assign load to node */
            schedulingState.updateTrackingData(node, lbConfig.loadStrategy)
            return Some(node.invoker)
          }
        }
        /* went around enough, give up */
        node = schedulingState._consistentHashList(Random.nextInt(schedulingState._consistentHashList.size))
        if (max_chain > 0) {
          logging.info(this, s"Activation ${activationId} was pushed full circle ${max_chain} places; randomly sending to ${node.invoker}, from ${original_node.invoker}")(transId)
          schedulingState.wakeUpInvoker()
        }
        schedulingState.updateTrackingData(node, lbConfig.loadStrategy)
        return Some(node.invoker)
      }
      case None => None
    }
  }
}
