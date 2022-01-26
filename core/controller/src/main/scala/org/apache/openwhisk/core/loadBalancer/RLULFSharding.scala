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
// import java.util.concurrent.ThreadLocalRandom

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
import java.util.concurrent.atomic.LongAdder
import java.time.Instant
import org.apache.commons.math3.distribution.{NormalDistribution}
import org.apache.commons.math3.stat.descriptive.rank.Percentile
import scala.collection.concurrent.TrieMap
import scala.collection.mutable
import scala.math.{min} //, max}

class RLULFSharding(
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

    RLULFSharding.updateShardsPopular(action.fullyQualifiedName(true))
    val isBlackboxInvocation = action.exec.pull
    val actionType = if (!isBlackboxInvocation) "managed" else "blackbox"
    val (invokersToUse, stepSizes) = (schedulingState.invokers, schedulingState.managedStepSizes)
    val chosen = if (invokersToUse.nonEmpty) {
      val hash = RLULFSharding.generateHash(msg.user.namespace.name, action.fullyQualifiedName(false))
      val homeInvoker = hash % invokersToUse.size
      val stepSize = stepSizes(hash % stepSizes.size)
      val invoker: Option[(InvokerInstanceId, Boolean)] = RLULFSharding.schedule(
        action.limits.concurrency.maxConcurrent,
        msg.activationId,
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
    RLULFSharding.updatePopularity(schedulingState, lbConfig, totalActivations.longValue, first_invoke)
  }

  override def releaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry) = {
    schedulingState.invokerSlots
      .lift(invoker.toInt)
      .foreach(_.releaseConcurrent(entry.fullyQualifiedEntityName, entry.maxConcurrent, entry.memoryLimit.toMB.toInt))
  }
}

object RLULFSharding extends LoadBalancerProvider {

  private var popularity: mutable.Map[String, Long] = mutable.Map[String, Long]().withDefaultValue(0)
  private var popular: mutable.Map[String, Boolean] = mutable.Map[String, Boolean]().withDefaultValue(false)
  private var ratios: mutable.Map[String, Double] = mutable.Map[String, Double]().withDefaultValue(1.0)
  private val last_access_times : TrieMap[String, Long] = TrieMap.empty[String, Long]
  private val inter_arival_times : TrieMap[String, Double] = TrieMap.empty[String, Double]
  private var load_distrib : NormalDistribution = null
  private var load_per_invoke : Double = 0.0
  private val percentile_popular : Double = 20.0
  private var popular_threshold : Double = 0.0
  private var avg_arrival_rate : Double = 0.0
  private var ema_alph : Double = 0.9
  private var starts : LongAdder = new LongAdder()

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
    new RLULFSharding(
      whiskConfig,
      instance,
      createFeedFactory(whiskConfig, instance),
      invokerPoolFactory)
  }

  def requiredProperties: Map[String, String] = kafkaHosts

  def now() : Long = {
    Instant.now().toEpochMilli()
  }

  def updatePopularity(schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig, totalActivations: Long, first_invoke : Option[Long])(implicit logging: Logging) : Unit = {
    logging.info(this, s"calculating popularity")(TransactionId.invokerRedis)
    val p = new Percentile()
    val list = inter_arival_times.values.toArray.sorted
    popular_threshold =  p.evaluate(list, percentile_popular) // percentile(list, percentile_popular)
    val avg_iat = p.evaluate(list, 50.0)
    avg_arrival_rate = 1.0 / (avg_iat/1000.0)
    logging.info(this, s"calculated popularity; avg_iat = ${avg_iat}; avg_arrival_rate = ${avg_arrival_rate}; popular_threshold=${popular_threshold}; iats = ${inter_arival_times}, times = ${last_access_times}")(TransactionId.invokerRedis)

    var state = inter_arival_times.keys.iterator.foldLeft("") { (agg, curr) =>
      val iat = inter_arival_times(curr)
      val pop = iat <= popular_threshold
      popular += (curr -> pop)
      agg + s"${curr} has IAT of ${iat} and is popular? ${pop}; "
    }
    logging.info(this, state)(TransactionId.invokerRedis)

    val s = 1
    val server_arrival_rate = avg_arrival_rate  / schedulingState.invokers.size
    // var extra_anticip_load = server_arrival_rate / lbConfig.invoker.cores * s 

    // Let Lambda=server arrival rate/#cores, so we are saying that extra anticip load is Lambda * staleness (==1 minute) . 
    // Now, this is not strictly true, because it needs to be normalized by how long each function takes to finish. 
    // Let the observed load be L. This correponds to a historic arrival rate of Lambda-hist. So the load-per-invok is L/Lambda-hist. 
    // The extra load thus should be load-per-invok*server_arrival_rate. This was in my uncommitted simulator. Sorry :( 
    // Implementation wise, for computing historic average arrival rate, just increment total number of invoks 
    // (probably doing that somewhere anyways?), and divide by elapsed time from first invok to current time.
    var lambda = server_arrival_rate / lbConfig.invoker.cores
    val lambda_hist = first_invoke match {
      case Some(time) => {
        totalActivations.toDouble / ((now() - time) / 1000.0)
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
    var extra_anticip_load : Double = (server_arrival_rate / lbConfig.invoker.cores) * 10

    logging.info(this, s"avg_arrival_rate: ${avg_arrival_rate}; server_arrival_rate: ${server_arrival_rate}; extra_anticip_load: ${extra_anticip_load}; tot_load: ${tot_load}; avg_load: ${avg_load}; lambda_hist: ${lambda_hist}; num_invokers: ${schedulingState._consistentHashList.size}, load_per_invoke: ${load_per_invoke};")(TransactionId.invokerRedis)
    extra_anticip_load = min(extra_anticip_load, 0.2)
    // val distrib = new NormalDistribution(server_arrival_rate*lbConfig.invoker.boundedCeil, 0.1*lbConfig.invoker.boundedCeil)
    if (!extra_anticip_load.isNaN()) {
      load_distrib = new NormalDistribution(extra_anticip_load, 0.1)
    }
  }

  def updateShardsPopular(fqn: FullyQualifiedEntityName)(implicit logging: Logging, transid: TransactionId) : Unit = {
    val strName = s"${fqn.namespace}/${fqn.name}"
    val P = 100.0    
    val T = 100.0
    val r_orig = T/P // Effective sampling rate 
    if (true) {
      // logging.info(this, s"updating SHARDS popularity IAT for function ${strName}")(transid)

      val found = last_access_times get strName
      found match {
        case Some(last_access_time) => {
          val curr_t = now()
          val iat = (curr_t - last_access_time) / r_orig
          var ema_iat = inter_arival_times.getOrElse(strName, iat)
          ema_iat = (iat * ema_alph) + ((1-ema_alph) * ema_iat)
          last_access_times += (strName -> curr_t)
          inter_arival_times += (strName -> ema_iat)
          // logging.info(this, s"new SHARDS popularity IAT for function ${strName} = ${ema_iat}")(transid)
        }
        case None => {
          val curr_t = now()
          last_access_times += (strName -> curr_t)
          // logging.info(this, s"new SHARDS popularity access for function ${strName} at ${curr_t}")(transid)
        }
      }
    }
  }

  def tryStartInvoker(schedulingState: RedisAwareLoadBalancerState)(implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem) : Unit = {
    starts.increment()
    // logging.info(this, s"incrementing invoker start count")
    if (starts.sum() > 10) {
      // logging.info(this, s"asking to wake up invoker")
      starts.reset()
      schedulingState.wakeUpInvoker()
    }
  }

  def noisyLoad(load: Double)(implicit logging: Logging, transid: TransactionId) : Double = {
    if (load_distrib == null) {
      return load
    }
    return load + load_distrib.sample() // max(0.0, load_distrib.sample())
  }

  def runLocalOverloaded(invoker: InvokerInstanceId, schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig)
    (implicit logging: Logging, transid: TransactionId) : (Boolean, Double) = {

    // assume function is popular
    val load = schedulingState.getLoad(invoker, lbConfig.loadStrategy)
    val cutoff = schedulingState.getLoadCutoff(lbConfig.loadStrategy)
    val Lnoisy = noisyLoad(load)
    val ret = Lnoisy > cutoff
    logging.info(this, s"invoker ${invoker} over load? ${load} (${Lnoisy}) > ${cutoff} = ${ret}")
    return (ret, Lnoisy-load) 
  }

  /** Generates a hash based on the string representation of namespace and action */
  def generateHash(namespace: EntityName, action: FullyQualifiedEntityName): Int = {
    (namespace.asString.hashCode() ^ action.asString.hashCode()).abs
  }

  def shortWarmTime(name: String, schedulingState: RedisAwareLoadBalancerState)(implicit logging: Logging, transId: TransactionId) : Boolean = {
    val current_data = schedulingState.runTimes.getOrElse(name, (0.0, 0.0))
    logging.info(this, s"function ${name} has short warm time? ${current_data._1} ${current_data._1 < 1000}")
    if (current_data._1 != 0.0) {
      return current_data._1 < 500
    }
    else {
      // unknown warm time
      return false
    }
  }

  /**
   * Scans through all invokers and searches for an invoker tries to get a free slot on an invoker. If no slot can be
   * obtained, picks a healthy invoker by least loaded.
   *
   * @param aId 
   * @param invokers a list of available invokers to search in, including their state
   * @param dispatched semaphores for each invoker to give the slots away from
   * @param slots Number of slots, that need to be acquired (e.g. memory in MB)
   * @param index the index to start from (initially should be the "homeInvoker"
   * @param step stable identifier of the entity to be scheduled
   * @return an invoker to schedule to or None of no invoker is available
   */
  def schedule(maxConcurrent: Int,
    aId: ActivationId,
    fqn: FullyQualifiedEntityName,
    invokers: IndexedSeq[InvokerHealth],
    dispatched: IndexedSeq[NestedSemaphore[FullyQualifiedEntityName]],
    slots: Int,
    index: Int,
    step: Int,
    stepsDone: Int = 0,
    schedulingState: RedisAwareLoadBalancerState,
    lbConfig: ShardingContainerPoolBalancerConfig)
    (implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem): Option[(InvokerInstanceId, Boolean)] = {
   

    if (invokers.size > 0) {
      val strName = s"${fqn.namespace}/${fqn.name}"
      val invoker = invokers(index).id

      if (popular(strName)) {
        return schedulePop(maxConcurrent, aId, fqn, strName, invokers, dispatched, slots, index, step, stepsDone, schedulingState, lbConfig)
      }
      else {
        return scheduleUnpop(maxConcurrent, aId, fqn, strName, invokers, dispatched, slots, index, step, stepsDone, schedulingState, lbConfig)
      }
    }
    else {
      return None
    }
  }

  def leastLoad(invokers: IndexedSeq[InvokerHealth], schedulingState: RedisAwareLoadBalancerState, lbConfig: ShardingContainerPoolBalancerConfig) : InvokerHealth = {
    invokers.filter(invoker => invoker.status.isUsable).reduceLeft((left, right) =>
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

  @tailrec
  def schedulePop(maxConcurrent: Int,
    aId: ActivationId,
    fqn: FullyQualifiedEntityName,
    strName: String,
    invokers: IndexedSeq[InvokerHealth],
    dispatched: IndexedSeq[NestedSemaphore[FullyQualifiedEntityName]],
    slots: Int,
    index: Int,
    step: Int,
    stepsDone: Int = 0,
    schedulingState: RedisAwareLoadBalancerState,
    lbConfig: ShardingContainerPoolBalancerConfig)
    (implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem): Option[(InvokerInstanceId, Boolean)] = {

    if (stepsDone > lbConfig.maxChainLen) {
      tryStartInvoker(schedulingState)
      val ll = leastLoad(invokers, schedulingState, lbConfig).id
      logging.warn(this, s"system is overloaded. Chose invoker${ll.toInt} by least loaded assignment for popular ${aId}")
      dispatched(ll.toInt).forceAcquireConcurrent(fqn, maxConcurrent, slots)
      schedulingState.incrementLoad(ll, load_distrib.sample())
      return Some(ll, true)
    }

    val invoker = invokers(index)

    if (invoker.status.isUsable) {
      val (localOverloaded, extra_anticip_load) = runLocalOverloaded(invoker.id, schedulingState, lbConfig)
      if (!localOverloaded && dispatched(invoker.id.toInt).tryAcquireConcurrent(fqn, maxConcurrent, slots)) {
        if (stepsDone > 0) {
          logging.info(this, s"pushed popular invocation ${stepsDone} places for ${aId}")
        }
        return Some(invoker.id, false)
      }
      else {
        val newIndex = (index + step) % invokers.size
        return schedulePop(maxConcurrent, aId, fqn, strName, invokers, dispatched, slots, newIndex, step, stepsDone+1, schedulingState, lbConfig)
      }
    } else {
      // jump to next invoker if unhealthy
      val newIndex = (index + step) % invokers.size
      return schedulePop(maxConcurrent, aId, fqn, strName, invokers, dispatched, slots, newIndex, step, stepsDone, schedulingState, lbConfig)
    }
  }

  @tailrec
  def scheduleUnpop(maxConcurrent: Int,
    aId: ActivationId,
    fqn: FullyQualifiedEntityName,
    strName: String,
    invokers: IndexedSeq[InvokerHealth],
    dispatched: IndexedSeq[NestedSemaphore[FullyQualifiedEntityName]],
    slots: Int,
    index: Int,
    step: Int,
    stepsDone: Int = 0,
    schedulingState: RedisAwareLoadBalancerState,
    lbConfig: ShardingContainerPoolBalancerConfig)
    (implicit logging: Logging, transId: TransactionId, actorSystem: ActorSystem): Option[(InvokerInstanceId, Boolean)] = {

    if (stepsDone > lbConfig.maxChainLen) {
      tryStartInvoker(schedulingState)
      val ll = leastLoad(invokers, schedulingState, lbConfig).id
      logging.warn(this, s"system is overloaded. Chose invoker${ll.toInt} by least loaded assignment for unpopular ${aId}")
      dispatched(ll.toInt).forceAcquireConcurrent(fqn, maxConcurrent, slots)
      schedulingState.incrementLoad(ll, load_distrib.sample())
      return Some(ll, true)
    }

    val invoker = invokers(index)

    if (invoker.status.isUsable) {
      val serverLoad = schedulingState.getLoad(invoker.id, lbConfig.loadStrategy)
      if (serverLoad <= lbConfig.invoker.boundedCeil && dispatched(invoker.id.toInt).tryAcquireConcurrent(fqn, maxConcurrent, slots)) {
        if (stepsDone > 0) {
          logging.info(this, s"unpopular Activation was pushed ${stepsDone} places to ${invoker.id} for ${aId}")(transId)
        }
        return Some(invoker.id, true)
      } else {
        val newIndex = (index + step) % invokers.size
        return scheduleUnpop(maxConcurrent, aId, fqn, strName, invokers, dispatched, slots, newIndex, step, stepsDone+1, schedulingState, lbConfig)
      }
    } else {
      // jump to next invoker if unhealthy
      val newIndex = (index + step) % invokers.size
      return scheduleUnpop(maxConcurrent, aId, fqn, strName, invokers, dispatched, slots, newIndex, step, stepsDone, schedulingState, lbConfig)
    }
  }
}
