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
import org.apache.commons.math3.distribution.{NormalDistribution, UniformRealDistribution}
import scala.collection.mutable
// import scala.concurrent.duration._
import java.util.concurrent.atomic.LongAdder
import org.apache.openwhisk.core.{ConfigKeys, WhiskConfig}
import pureconfig._
import pureconfig.generic.auto._

/**
 * A loadbalancer that schedules workload based on random-forwarding consistent hashing load balancer
 */
class RandomForwardLoadBalancer(
  config: WhiskConfig,
  controllerInstance: ControllerInstanceId,
  feedFactory: FeedFactory,
  invokerPoolFactory: InvokerPoolFactory,
  messagingProvider: MessagingProvider = SpiLoader.get[MessagingProvider])(
  implicit actorSystem: ActorSystem,
  logging: Logging)
    extends RedisAwareLoadBalancer(config, controllerInstance, feedFactory, invokerPoolFactory) {

  private val probabliltyState = RandomGenerationState()(lbConfig)

  /** 1. Publish a message to the loadbalancer */
  override def publish(action: ExecutableWhiskActionMetaData, msg: ActivationMessage)(
    implicit transid: TransactionId) : Future[Future[Either[ActivationId, WhiskActivation]]] = {

      val chosen = RandomForwardLoadBalancer.schedule(action.fullyQualifiedName(true),
                                                        schedulingState, 
                                                        msg.activationId, 
                                                        lbConfig.loadStrategy,
                                                        probabliltyState)

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
    probabliltyState.updateInvokerLoad(schedulingState, lbConfig.loadStrategy)
    RandomForwardLoadBalancer.updatePopularity(schedulingState)
  }
}

case class RandomGenerationState()
(
  lbConfig: ShardingContainerPoolBalancerConfig =
    loadConfigOrThrow[ShardingContainerPoolBalancerConfig](ConfigKeys.loadbalancer))(implicit logging: Logging) {

  private val load_range : IndexedSeq[BigDecimal] = Range.BigDecimal(0.0, 10.0*lbConfig.invoker.boundedCeil, 0.01)
  private val distrib : NormalDistribution = new NormalDistribution(0.5*lbConfig.invoker.boundedCeil, 0.1*lbConfig.invoker.boundedCeil)

  private val transformed_load_range : IndexedSeq[Double] = load_range.map(x => distrib.cumulativeProbability(x.doubleValue))
  private val invoker_transformed_loads : mutable.Map[InvokerInstanceId, Double] = mutable.Map[InvokerInstanceId, Double]().withDefaultValue(0.0)
  private val uniform_distrib : UniformRealDistribution = new UniformRealDistribution(0.0, 1.0)

  logging.info(this, s"Load range from 0.0 to ${10.0*lbConfig.invoker.boundedCeil}")(TransactionId.invokerRandom)
  logging.info(this, s"NormalDistribution mean = ${0.5*lbConfig.invoker.boundedCeil} sd ${0.1*lbConfig.invoker.boundedCeil}")(TransactionId.invokerRandom)
  logging.info(this, s"UniformRealDistribution lower = ${0.0} sd ${1}")(TransactionId.invokerRandom)

  def searchSortedLoad(load: Double) : Double = {
    for (i <- 0 to load_range.size) {
      if (load_range(i) > load) {
        return transformed_load_range(i-1)
      }
    }
    return transformed_load_range(transformed_load_range.size -1)
  }

  def updateInvokerLoad(schedulingState: RedisAwareLoadBalancerState, loadStrategy: String)(implicit logging: Logging) : Unit = {
    logging.info(this, s"updating invoker load")(TransactionId.invokerRedis)
    schedulingState.invokers.map { invoker =>
      val serverLoad = schedulingState.getLoad(invoker.id, loadStrategy)
      invoker_transformed_loads += (invoker.id -> searchSortedLoad(serverLoad))
    }
  }

  def forwardProbability(invoker: InvokerInstanceId)(implicit logging: Logging, transid: TransactionId) : Boolean = {
    val prob = invoker_transformed_loads(invoker)
    val sample = uniform_distrib.sample()
    return sample < prob
  }

}

object RandomForwardLoadBalancer extends LoadBalancerProvider {

  private var popularity: mutable.Map[String, Long] = mutable.Map[String, Long]().withDefaultValue(0)
  private var popular: mutable.Map[String, Boolean] = mutable.Map[String, Boolean]().withDefaultValue(false)
  private var ratios: mutable.Map[String, Double] = mutable.Map[String, Double]().withDefaultValue(1.0)
  val totalActivations = new LongAdder()

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
    new RandomForwardLoadBalancer(
      whiskConfig,
      instance,
      createFeedFactory(whiskConfig, instance),
      invokerPoolFactory)
  }

  def updatePopularity(schedulingState: RedisAwareLoadBalancerState)(implicit logging: Logging) : Unit = {
    logging.info(this, s"calculating popularity")(TransactionId.invokerRedis)

    val actsLong = totalActivations.longValue.toDouble
    if (actsLong > 0) {
      var cutoff : Double = 1.0
      if (schedulingState.runTimes.size > 0) {
        cutoff = 1.0 / schedulingState.runTimes.size.toDouble
      }
      // logging.info(this, s"There are ${popularity.size} funcs in system")(TransactionId.invokerRedis)
      var sorted = popularity.toList.sortBy(item => item._2.longValue)
      var state = sorted.iterator.foldLeft("") { (agg, curr) =>
        val ratio : Double = curr._2.longValue / actsLong
        ratios += (curr._1 -> ratio)
        val pop = ratio >= cutoff
        popular += (curr._1 -> pop)
        agg + s"${curr._1} has '${curr._2}' invokes out of ${actsLong} total for a ratio of $ratio and is popular? ${ratio >= cutoff}; "
      }
      logging.info(this, s"popularity cutoff is $cutoff; Popularity state is: $state")(TransactionId.invokerRedis)
    }
  }

  def requiredProperties: Map[String, String] = kafkaHosts

  def isPopular(schedulingState: RedisAwareLoadBalancerState,name: String)(implicit logging: Logging, transid: TransactionId) : Boolean = {
    return popular(name)
    // val pop = popularity(name).longValue.toDouble
    // val ratio : Double = pop / totalActivations.longValue
    // val cutoff : Double = 1.0 / schedulingState.runTimes.size.toDouble
    // // logging.info(this, s"checking popularity ${name} $ratio >= $cutoff => ${ratio >= cutoff}")
    // return ratio >= cutoff
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
    loadStrategy: String,
    probabliltyState: RandomGenerationState)
    (implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem) : Option[InvokerInstanceId] = {
    totalActivations.increment()      
    // logging.info(this, s"Scheduling action '${fqn}' with TransactionId ${transId}")(transId)

    val strName = s"${fqn.namespace}/${fqn.name}"
    val func_pop = popularity(strName) + 1//.increment()
    popularity += (strName -> func_pop)
    if (! isPopular(schedulingState, strName)) {
      // logging.info(this, s"unpopular function ${strName} :(")(transId)
      return getInvokerConsistentCache(fqn, schedulingState, activationId, loadStrategy)
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
          val serverLoad = schedulingState.getLoad(node, loadStrategy)

          val should_forward = probabliltyState.forwardProbability(node.invoker)
          if (! should_forward) {
            if (chain_len > 0) {
              logging.info(this, s"Activation ${activationId} was pushed ${chain_len} places to ${node.invoker}, from ${orig_invoker}")(transId)
            }
            // logging.info(this, s"Not forwarding from invoker ${node.invoker}, load: ${serverLoad}")(transId)
            schedulingState.updateTrackingData(node, loadStrategy)
            return Some(node.invoker)
          }
          // logging.info(this, s"forwarding from invoker ${node.invoker}, load: ${serverLoad}")(transId)
          chain_len += 1
        }
        /* went around enough, give up */
        if (chain_len > 0) {
          logging.info(this, s"Activation ${activationId} was pushed full circle ${chain_len} places to ${node.invoker}, from ${orig_invoker}")(transId)
          schedulingState.wakeUpInvoker()
        }
        schedulingState.updateTrackingData(node, loadStrategy)
        return Some(node.invoker)
      }
      case None => None
    }
  }

  def getInvokerConsistentCache(
    fqn: FullyQualifiedEntityName, 
    schedulingState: RedisAwareLoadBalancerState, 
    activationId: ActivationId, 
    loadStrategy: String)(implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem) : Option[InvokerInstanceId] = {
    
    val strName = s"${fqn.namespace}/${fqn.name}"
    val possNode = schedulingState.locateNode(strName)
    possNode match {
      case Some (foundNode) => {
        var original_node = foundNode
        val orig_serverLoad = schedulingState.getLoad(original_node, loadStrategy)
        var node = original_node
        val loadCuttoff = schedulingState.getLoadCutoff(loadStrategy)

        val idx = schedulingState._consistentHashList.indexWhere( p => p.invoker == original_node.invoker)
        val chainLen = schedulingState.invokers.length
        var times = schedulingState.runTimes.getOrElse(strName, (0.0, 0.0))
        var r: Double = 2.2
        if (times._1 != 0.0) {
          r = times._2 / times._1
          r = min(r, 2.2)
        }

        for (i <- 0 to chainLen) {
          var id = (idx + i) % schedulingState.invokers.length
          node = schedulingState._consistentHashList(id)
          val serverLoad = schedulingState.getLoad(node, loadStrategy)

          if (serverLoad <= loadCuttoff) {
            if (i > 0) {
              logging.info(this, s"unpopular Activation ${activationId} was pushed ${i} places to ${node.invoker}, from ${original_node.invoker}")(transId)
            }
            /* assign load to node */
            schedulingState.updateTrackingData(node, loadStrategy)
            return Some(node.invoker)
          }
          else if (serverLoad <= r-1) {
            if (i > 0) {
              logging.info(this, s"unpopular Activation ${activationId} was pushed ${i} places to ${node.invoker}, from ${original_node.invoker}")(transId)
            }
            schedulingState.updateTrackingData(node, loadStrategy)
            return Some(node.invoker)
          }
        }
        logging.info(this, s"unpopular Activation ${activationId} was pushed back around to original node, ${original_node.invoker}")(transId)
        schedulingState.wakeUpInvoker()
        /* went around enough, give up */
        schedulingState.updateTrackingData(original_node, loadStrategy)
        return Some(original_node.invoker)
      }
      case None => None
    }
  }
}
