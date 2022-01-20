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
import org.apache.openwhisk.core.controller.Controller
import org.apache.openwhisk.core.{WhiskConfig}
import org.apache.openwhisk.spi.SpiLoader

import scala.concurrent.Future
// import java.util.concurrent.atomic.LongAdder
import java.time.Instant


class LeastLoadBalancer(
  config: WhiskConfig,
  controllerInstance: ControllerInstanceId,
  feedFactory: FeedFactory,
  invokerPoolFactory: InvokerPoolFactory,
  messagingProvider: MessagingProvider = SpiLoader.get[MessagingProvider])(
  implicit actorSystem: ActorSystem,
  logging: Logging)
    extends RedisAwareLoadBalancer(config, controllerInstance, feedFactory, invokerPoolFactory) {

  private var first_invoke : Option[Long] = None

  /** 1. Publish a message to the loadbalancer */
  override def publish(action: ExecutableWhiskActionMetaData, msg: ActivationMessage)(
    implicit transid: TransactionId): Future[Future[Either[ActivationId, WhiskActivation]]] = {

    if (first_invoke.isEmpty) {
      first_invoke = Some(Instant.now().toEpochMilli())
    }

    val isBlackboxInvocation = action.exec.pull
    val actionType = if (!isBlackboxInvocation) "managed" else "blackbox"
    val (invokersToUse, stepSizes) = (schedulingState.invokers, schedulingState.managedStepSizes)
    val chosen = if (invokersToUse.nonEmpty) {
      val invoker: Option[(InvokerInstanceId, Boolean)] = LeastLoadBalancer.schedule(
        invokersToUse,
        schedulingState,
        lbConfig)
      invoker.foreach {
        case (_, true) =>
          val metric =
            if (isBlackboxInvocation)
              LoggingMarkers.BLACKBOX_SYSTEM_OVERLOAD
            else
              LoggingMarkers.MANAGED_SYSTEM_OVERLOAD
          MetricEmitter.emitCounterMetric(metric)
        case _ =>
      }
      invoker.map(_._1)
    } else {
      None
    }

    chosen
      .map { invoker =>
        // MemoryLimit() and TimeLimit() return singletons - they should be fast enough to be used here
        val memoryLimit = action.limits.memory
        val memoryLimitInfo = if (memoryLimit == MemoryLimit()) { "std" } else { "non-std" }
        val timeLimit = action.limits.timeout
        val timeLimitInfo = if (timeLimit == TimeLimit()) { "std" } else { "non-std" }
        logging.info(
          this,
          s"scheduled activation ${msg.activationId}, action '${msg.action.asString}' ($actionType), ns '${msg.user.namespace.name.asString}', mem limit ${memoryLimit.megabytes} MB (${memoryLimitInfo}), time limit ${timeLimit.duration.toMillis} ms (${timeLimitInfo}) to ${invoker}")
        val activationResult = setupActivation(msg, action, invoker)
        sendActivationToInvoker(messageProducer, msg, invoker).map(_ => activationResult)
      }
      .getOrElse {
        // report the state of all invokers
        val invokerStates = invokersToUse.foldLeft(Map.empty[InvokerState, Int]) { (agg, curr) =>
          val count = agg.getOrElse(curr.status, 0) + 1
          agg + (curr.status -> count)
        }

        logging.error(
          this,
          s"failed to schedule activation ${msg.activationId}, action '${msg.action.asString}' ($actionType), ns '${msg.user.namespace.name.asString}' - invokers to use: $invokerStates")
        Future.failed(LoadBalancerException("No invokers available"))
      }
  }

  override protected def customUpdate() : Unit = {
    RandomLoadUpdateBalancer.updatePopularity(schedulingState, lbConfig)
  }

  override def releaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry) = {
    schedulingState.invokerSlots
      .lift(invoker.toInt)
      .foreach(_.releaseConcurrent(entry.fullyQualifiedEntityName, entry.maxConcurrent, entry.memoryLimit.toMB.toInt))
  }
}

object LeastLoadBalancer extends LoadBalancerProvider {

  private var load_per_invoke : Double = 0.0

  override def instance(whiskConfig: WhiskConfig, instance: ControllerInstanceId)(implicit actorSystem: ActorSystem,
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
            messagingProvider.getConsumer(
              whiskConfig,
              s"${Controller.topicPrefix}health${instance.asString}",
              s"${Controller.topicPrefix}health",
              maxPeek = 128),
            monitor))
      }

    }
    new LeastLoadBalancer(
      whiskConfig,
      instance,
      createFeedFactory(whiskConfig, instance),
      invokerPoolFactory)
  }

  def requiredProperties: Map[String, String] = kafkaHosts

  def updatePopularity(schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig, totalActivations: Long, first_invoke: Option[Long])
    (implicit logging: Logging) : Unit = {
    var avg_arrival_rate = 0.0
    var server_arrival_rate = 0.0 // avg_arrival_rate  / schedulingState.invokers.size

    // Let Lambda=server arrival rate/#cores, so we are saying that extra anticip load is Lambda * staleness (==1 minute) . 
    // Now, this is not strictly true, because it needs to be normalized by how long each function takes to finish. 
    // Let the observed load be L. This correponds to a historic arrival rate of Lambda-hist. So the load-per-invok is L/Lambda-hist. 
    // The extra load thus should be load-per-invok*server_arrival_rate. This was in my uncommitted simulator. Sorry :( 
    // Implementation wise, for computing historic average arrival rate, just increment total number of invoks 
    // (probably doing that somewhere anyways?), and divide by elapsed time from first invok to current time.
    val lambda_hist = first_invoke match {
      case Some(time) => {
        avg_arrival_rate = totalActivations.toDouble / ((Instant.now().toEpochMilli() - time) / 1000.0) 
        server_arrival_rate = avg_arrival_rate  / schedulingState.invokers.size
        avg_arrival_rate
      }
      case None => 0.0
    }
    var tot_load = 0.0

    for (invoker <- schedulingState.invokers)
    {
      val load = schedulingState.getLoad(invoker.id, lbConfig.loadStrategy)
      tot_load = load + tot_load 
    }
    val avg_load = tot_load / schedulingState.invokers.size
    load_per_invoke = avg_load / lambda_hist
  }

  def leastLoad(invokers: IndexedSeq[InvokerHealth], schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig) : InvokerHealth = {
    invokers.reduceLeft((left, right) =>
      {
        val ll = schedulingState.getLoad(left.id, lbConfig.loadStrategy)
        val rl = schedulingState.getLoad(right.id, lbConfig.loadStrategy)
        if (ll > rl) {
          right
        }
        else {
          left
        }
      }
    )
  }

  /**
   * Scans through all invokers and searches for an invoker tries to get a free slot on an invoker. If no slot can be
   * obtained, randomly picks a healthy invoker.
   *
   * @param maxConcurrent concurrency limit supported by this action
   * @param invokers a list of available invokers to search in, including their state
   * @param dispatched semaphores for each invoker to give the slots away from
   * @param slots Number of slots, that need to be acquired (e.g. memory in MB)
   * @param index the index to start from (initially should be the "homeInvoker"
   * @param step stable identifier of the entity to be scheduled
   * @return an invoker to schedule to or None of no invoker is available
   */
  def schedule(
    invokers: IndexedSeq[InvokerHealth],
    schedulingState: RedisAwareLoadBalancerState,
    lbConfig: ShardingContainerPoolBalancerConfig)(implicit logging: Logging, transId: TransactionId): Option[(InvokerInstanceId, Boolean)] = {

    if (invokers.size > 0) {
      val invoker = leastLoad(invokers, schedulingState, lbConfig)
      schedulingState.incrementLoad(invoker.id, load_per_invoke)
      Some(invoker.id, false)
    } else {
      None
    }
  }
}
