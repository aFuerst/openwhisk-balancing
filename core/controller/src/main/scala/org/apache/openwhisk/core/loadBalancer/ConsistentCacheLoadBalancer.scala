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
/**
 * A loadbalancer that schedules workload based on power-of-two consistent hashing-algorithm.
 */
class ConsistentCacheLoadBalancer(
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
    schedulingState: RedisAwareLoadBalancerState,
    activationId: ActivationId,
    loadStrategy: String,
    algo: String)
    (implicit logging: Logging, transId: TransactionId): Option[InvokerInstanceId] = {
      // logging.info(this, s"Scheduling action '${fqn}' with TransactionId ${transId}")

      val strName = s"${fqn.namespace}/${fqn.name}"
      val possNode = schedulingState._consistentHash.locate(strName)
      if (possNode.isPresent)
      {
        var original_node = possNode.get()
        val orig_serverLoad = schedulingState.getLoad(original_node, loadStrategy)
        var node = original_node
        val loadCuttoff = schedulingState.getLoadCutoff(loadStrategy)

        val idx = schedulingState._consistentHashList.indexWhere( p => p.invoker == original_node.invoker)
        val chainLen = schedulingState.invokers.length // min(_invokers.length, loadCuttoff).toInt
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
            // logging.info(this, s"Invoker ${original_node.invoker} overloaded with $orig_serverLoad, assigning work to node under cutoff ${node.invoker}")
            /* assign load to node */
            schedulingState.updateTrackingData(node)
            return Some(node.invoker)
          }
          else if (serverLoad <= r-1) {
            // logging.info(this, s"Invoker ${original_node.invoker} overloaded with $orig_serverLoad, assigning work to node with load under $r - 1 ${node.invoker}")
            schedulingState.updateTrackingData(node)
            return Some(node.invoker)
          }
        }
        /* went around enough, give up */
        schedulingState.updateTrackingData(node)
        return Some(node.invoker)
      }
      else None
    }
}
