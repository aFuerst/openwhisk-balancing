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
import java.util.concurrent.ThreadLocalRandom

import akka.actor.{ActorSystem}
import org.apache.kafka.clients.producer.RecordMetadata
import org.apache.openwhisk.common._
import org.apache.openwhisk.core.WhiskConfig._
import org.apache.openwhisk.core.connector._
import org.apache.openwhisk.core.entity._
import org.apache.openwhisk.core.controller.Controller
import org.apache.openwhisk.core.{WhiskConfig}
import org.apache.openwhisk.spi.SpiLoader

import scala.annotation.tailrec
import scala.concurrent.Future
// import java.util.concurrent.atomic.LongAdder
import java.time.Instant
import org.apache.commons.math3.distribution.{NormalDistribution}
import scala.math.{min}

/**
 * A loadbalancer that schedules workload based on a hashing-algorithm.
 *
 * ## Algorithm
 *
 * At first, for every namespace + action pair a hash is calculated and then an invoker is picked based on that hash
 * (`hash % numInvokers`). The determined index is the so called "home-invoker". This is the invoker where the following
 * progression will **always** start. If this invoker is healthy (see "Invoker health checking") and if there is
 * capacity on that invoker (see "Capacity checking"), the request is scheduled to it.
 *
 * If one of these prerequisites is not true, the index is incremented by a step-size. The step-sizes available are the
 * all coprime numbers smaller than the amount of invokers available (coprime, to minimize collisions while progressing
 * through the invokers). The step-size is picked by the same hash calculated above (`hash & numStepSizes`). The
 * home-invoker-index is now incremented by the step-size and the checks (healthy + capacity) are done on the invoker
 * we land on now.
 *
 * This procedure is repeated until all invokers have been checked at which point the "overload" strategy will be
 * employed, which is to choose a healthy invoker randomly. In a steadily running system, that overload means that there
 * is no capacity on any invoker left to schedule the current request to.
 *
 * If no invokers are available or if there are no healthy invokers in the system, the loadbalancer will return an error
 * stating that no invokers are available to take any work. Requests are not queued anywhere in this case.
 *
 * An example:
 * - availableInvokers: 10 (all healthy)
 * - hash: 13
 * - homeInvoker: hash % availableInvokers = 13 % 10 = 3
 * - stepSizes: 1, 3, 7 (note how 2 and 5 is not part of this because it's not coprime to 10)
 * - stepSizeIndex: hash % numStepSizes = 13 % 3 = 1 => stepSize = 3
 *
 * Progression to check the invokers: 3, 6, 9, 2, 5, 8, 1, 4, 7, 0 --> done
 *
 * This heuristic is based on the assumption, that the chance to get a warm container is the best on the home invoker
 * and degrades the more steps you make. The hashing makes sure that all loadbalancers in a cluster will always pick the
 * same home invoker and do the same progression for a given action.
 *
 * Known caveats:
 * - This assumption is not always true. For instance, two heavy workloads landing on the same invoker can override each
 *   other, which results in many cold starts due to all containers being evicted by the invoker to make space for the
 *   "other" workload respectively. Future work could be to keep a buffer of invokers last scheduled for each action and
 *   to prefer to pick that one. Then the second-last one and so forth.
 *
 * ## Capacity checking
 *
 * The maximum capacity per invoker is configured using `user-memory`, which is the maximum amount of memory of actions
 * running in parallel on that invoker.
 *
 * Spare capacity is determined by what the loadbalancer thinks it scheduled to each invoker. Upon scheduling, an entry
 * is made to update the books and a slot for each MB of the actions memory limit in a Semaphore is taken. These slots
 * are only released after the response from the invoker (active-ack) arrives **or** after the active-ack times out.
 * The Semaphore has as many slots as MBs are configured in `user-memory`.
 *
 * Known caveats:
 * - In an overload scenario, activations are queued directly to the invokers, which makes the active-ack timeout
 *   unpredictable. Timing out active-acks in that case can cause the loadbalancer to prematurely assign new load to an
 *   overloaded invoker, which can cause uneven queues.
 * - The same is true if an invoker is extraordinarily slow in processing activations. The queue on this invoker will
 *   slowly rise if it gets slow to the point of still sending pings, but handling the load so slowly, that the
 *   active-acks time out. The loadbalancer again will think there is capacity, when there is none.
 *
 * Both caveats could be solved in future work by not queueing to invoker topics on overload, but to queue on a
 * centralized overflow topic. Timing out an active-ack can then be seen as a system-error, as described in the
 * following.
 *
 * ## Invoker health checking
 *
 * Invoker health is determined via a kafka-based protocol, where each invoker pings the loadbalancer every second. If
 * no ping is seen for a defined amount of time, the invoker is considered "Offline".
 *
 * Moreover, results from all activations are inspected. If more than 3 out of the last 10 activations contained system
 * errors, the invoker is considered "Unhealthy". If an invoker is unhealthy, no user workload is sent to it, but
 * test-actions are sent by the loadbalancer to check if system errors are still happening. If the
 * system-error-threshold-count in the last 10 activations falls below 3, the invoker is considered "Healthy" again.
 *
 * To summarize:
 * - "Offline": Ping missing for > 10 seconds
 * - "Unhealthy": > 3 **system-errors** in the last 10 activations, pings arriving as usual
 * - "Healthy": < 3 **system-errors** in the last 10 activations, pings arriving as usual
 *
 * ## Horizontal sharding
 *
 * Sharding is employed to avoid both loadbalancers having to share any data, because the metrics used in scheduling
 * are very fast changing.
 *
 * Horizontal sharding means, that each invoker's capacity is evenly divided between the loadbalancers. If an invoker
 * has at most 16 slots available (invoker-busy-threshold = 16), those will be divided to 8 slots for each loadbalancer
 * (if there are 2).
 *
 * If concurrent activation processing is enabled (and concurrency limit is > 1), accounting of containers and
 * concurrency capacity per container will limit the number of concurrent activations routed to the particular
 * slot at an invoker. Default max concurrency is 1.
 *
 * Known caveats:
 * - If a loadbalancer leaves or joins the cluster, all state is removed and created from scratch. Those events should
 *   not happen often.
 * - If concurrent activation processing is enabled, it only accounts for the containers that the current loadbalancer knows.
 *   So the actual number of containers launched at the invoker may be less than is counted at the loadbalancer, since
 *   the invoker may skip container launch in case there is concurrent capacity available for a container launched via
 *   some other loadbalancer.
 */
class RLUShardingBalancer(
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
      val hash = RLUShardingBalancer.generateHash(msg.user.namespace.name, action.fullyQualifiedName(false))
      val homeInvoker = hash % invokersToUse.size
      val stepSize = stepSizes(hash % stepSizes.size)
      val invoker: Option[(InvokerInstanceId, Boolean)] = RLUShardingBalancer.schedule(
        action.limits.concurrency.maxConcurrent,
        action.fullyQualifiedName(true),
        invokersToUse,
        schedulingState.invokerSlots,
        action.limits.memory.megabytes,
        homeInvoker,
        stepSize,
        0,
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
    RLUShardingBalancer.updatePopularity(schedulingState, lbConfig, totalActivations.longValue, first_invoke)
  }

  override def releaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry) = {
    schedulingState.invokerSlots
      .lift(invoker.toInt)
      .foreach(_.releaseConcurrent(entry.fullyQualifiedEntityName, entry.maxConcurrent, entry.memoryLimit.toMB.toInt))
  }
}

object RLUShardingBalancer extends LoadBalancerProvider {

  private var load_distrib : NormalDistribution = null
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
    new RLUShardingBalancer(
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
    var extra_anticip_load = server_arrival_rate / load_per_invoke

    logging.info(this, s"avg_arrival_rate: ${avg_arrival_rate}; server_arrival_rate: ${server_arrival_rate}; extra_anticip_load: ${extra_anticip_load}; tot_load: ${tot_load}; avg_load: ${avg_load}; load_per_invoke: ${load_per_invoke};")(TransactionId.invokerRedis)
    extra_anticip_load = min(extra_anticip_load, 0.2)
    // val distrib = new NormalDistribution(server_arrival_rate*lbConfig.invoker.boundedCeil, 0.1*lbConfig.invoker.boundedCeil)
    load_distrib = new NormalDistribution(extra_anticip_load, 0.1)
  }

  def noisyLoad(load: Double)(implicit logging: Logging, transid: TransactionId) : Double = {
    if (load_distrib == null) {
      return load
    }
    return load + load_distrib.sample()
  }

  def underLoad(invoker: InvokerInstanceId, schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig)
    (implicit logging: Logging, transid: TransactionId) : Boolean = {

    // assume function is popular
    val load = schedulingState.getLoad(invoker, lbConfig.loadStrategy)
    val cutoff = schedulingState.getLoadCutoff(lbConfig.loadStrategy)
    val Lnoisy = noisyLoad(load)
    val ret = Lnoisy > cutoff
    // logging.info(this, s"invoker ${invoker} under load? ${load} < ${cutoff} = ${ret}")
    ret
  }

  /** Generates a hash based on the string representation of namespace and action */
  def generateHash(namespace: EntityName, action: FullyQualifiedEntityName): Int = {
    (namespace.asString.hashCode() ^ action.asString.hashCode()).abs
  }

  /** Euclidean algorithm to determine the greatest-common-divisor */
  @tailrec
  def gcd(a: Int, b: Int): Int = if (b == 0) a else gcd(b, a % b)

  /** Returns pairwise coprime numbers until x. Result is memoized. */
  def pairwiseCoprimeNumbersUntil(x: Int): IndexedSeq[Int] =
    (1 to x).foldLeft(IndexedSeq.empty[Int])((primes, cur) => {
      if (gcd(cur, x) == 1 && primes.forall(i => gcd(i, cur) == 1)) {
        primes :+ cur
      } else primes
    })


  def longWarmTime(name: String, schedulingState: RedisAwareLoadBalancerState)(implicit logging: Logging, transId: TransactionId) : Boolean = {
    val current_data = schedulingState.runTimes.getOrElse(name, (0.0, 0.0))
    // logging.info(this, s"function ${name} from ${schedulingState.runTimes} has long warm time? ${current_data._1} ${current_data._1 > 1000}")
    return current_data._1 > 1000
  }

  // def underLoad(invoker: InvokerHealth, schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig)
  //   (implicit logging: Logging, transId: TransactionId) : Boolean = {
    
  //   val load = schedulingState.getLoad(invoker.id, lbConfig.loadStrategy)
  //   val cutoff = schedulingState.getLoadCutoff(lbConfig.loadStrategy)
  //   val ret = load > cutoff
  //   // logging.info(this, s"invoker ${invoker} under load? ${load} < ${cutoff} = ${ret}")
  //   ret
  // }

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
  @tailrec
  def schedule(
    maxConcurrent: Int,
    fqn: FullyQualifiedEntityName,
    invokers: IndexedSeq[InvokerHealth],
    dispatched: IndexedSeq[NestedSemaphore[FullyQualifiedEntityName]],
    slots: Int,
    index: Int,
    step: Int,
    stepsDone: Int = 0,
    schedulingState: RedisAwareLoadBalancerState,
    lbConfig: ShardingContainerPoolBalancerConfig)(implicit logging: Logging, transId: TransactionId): Option[(InvokerInstanceId, Boolean)] = {
    val numInvokers = invokers.size
    val strName = s"${fqn.namespace}/${fqn.name}"

    if (numInvokers > 0) {
      val invoker = invokers(index)
      //test this invoker - if this action supports concurrency, use the scheduleConcurrent function
      if (invoker.status.isUsable && !(underLoad(invoker.id, schedulingState, lbConfig) && longWarmTime(strName, schedulingState)) && dispatched(invoker.id.toInt).tryAcquireConcurrent(fqn, maxConcurrent, slots)) {
        if (stepsDone > 0) {
          logging.info(this, s"pushed invocation ${stepsDone} places")
        }
        // schedulingState.incrementLoad(invoker.id, load_per_invoke)
        Some(invoker.id, false)
      } else {
        // If we've gone through all invokers
        if (stepsDone >= lbConfig.maxChainLen) {
          val healthyInvokers = invokers.filter(_.status.isUsable)
          if (healthyInvokers.nonEmpty) {
            // Choose a healthy invoker randomly
            val random = healthyInvokers(ThreadLocalRandom.current().nextInt(healthyInvokers.size)).id
            dispatched(random.toInt).forceAcquireConcurrent(fqn, maxConcurrent, slots)
            logging.warn(this, s"system is overloaded. Chose invoker${random.toInt} by random assignment.")
            // schedulingState.incrementLoad(random, load_per_invoke)
            Some(random, true)
          } else {
            None
          }
        } else {
          val newIndex = (index + step) % numInvokers
          schedule(maxConcurrent, fqn, invokers, dispatched, slots, newIndex, step, stepsDone + 1, schedulingState, lbConfig)
        }
      }
    } else {
      None
    }
  }
}
