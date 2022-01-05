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
import org.apache.openwhisk.core.{WhiskConfig}
import java.util.concurrent.ThreadLocalRandom
import scala.collection.concurrent.{TrieMap}
import scala.collection.mutable.Set
import java.util.concurrent.Semaphore

/**
 * A loadbalancer that schedules workload based on random-forwarding consistent hashing load balancer
 */
class GreedyBalancer(
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

      val chosen = GreedyBalancer.schedule(action.fullyQualifiedName(true),
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
}

object GreedyBalancer extends LoadBalancerProvider {

  private val semaphores : TrieMap[String, Semaphore] = TrieMap.empty[String, Semaphore]
  private val sets : TrieMap[String, scala.collection.mutable.Set[InvokerInstanceId]] = TrieMap.empty[String, scala.collection.mutable.Set[InvokerInstanceId]]
 
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
    new GreedyBalancer(
      whiskConfig,
      instance,
      createFeedFactory(whiskConfig, instance),
      invokerPoolFactory)
  }

  def requiredProperties: Map[String, String] = kafkaHosts

  def updateAssignedInvokers(actionName: String, invoker: InvokerInstanceId)(implicit logging: Logging, transId: TransactionId) {
    val sem = semaphores.getOrElseUpdate(actionName, new Semaphore(1))
    sem.acquire()
    val set = sets.getOrElseUpdate(actionName, scala.collection.mutable.Set())
    set += invoker
    logging.info(this, s"Updated invoker set to '${set}'")(transId)
    sem.release()
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

    val actionName = s"${fqn.namespace}/${fqn.name}"
    // logging.info(this, s"Scheduling action '${fqn}' with TransactionId ${transId}")(transId)
    
    val assignmets : Option[Set[InvokerInstanceId]] = sets get actionName
    assignmets match {
      case Some(set) => {
        val loads = set.map { invoker => (invoker,schedulingState.getLoad(invoker, lbConfig.loadStrategy)) }
        val minLoad = loads.minBy(_._2)
        if (minLoad._2 >= lbConfig.invoker.boundedCeil) {
          // previously assigned servers are overloaded, send to random one
          val random = schedulingState.invokers(ThreadLocalRandom.current().nextInt(schedulingState.invokers.size)).id
          logging.info(this, s"Previous servers are overloaded, assigning to random server '${random}'")(transId)
          updateAssignedInvokers(actionName, random)
          return Some(random)    
        }
        return Some(minLoad._1)
      }
      case None => {
        val random = schedulingState.invokers(ThreadLocalRandom.current().nextInt(schedulingState.invokers.size)).id
        logging.info(this, s"New function, assigning to random server '${random}'")(transId)
        updateAssignedInvokers(actionName, random)
        return Some(random)
      }
    }

    return None
  }
}
