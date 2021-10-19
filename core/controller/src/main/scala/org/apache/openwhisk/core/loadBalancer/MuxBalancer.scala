package org.apache.openwhisk.core.loadBalancer

// Original source from https://github.com/apache/openwhisk/pull/5091

import akka.actor.{ActorRef, ActorSystem, Props}
// import akka.stream.ActorMaterializer
import org.apache.openwhisk.common.{Logging, TransactionId}
import org.apache.openwhisk.core.{WhiskConfig}
import org.apache.openwhisk.core.WhiskConfig._
import org.apache.openwhisk.core.connector.{ActivationMessage, MessagingProvider}
import org.apache.openwhisk.core.entity._
import org.apache.openwhisk.common._
import org.apache.openwhisk.core.connector._
import org.apache.openwhisk.spi.SpiLoader
// import pureconfig.loadConfigOrThrow
// import spray.json._
// import pureconfig._
// import pureconfig.generic.auto._

import scala.concurrent.Future

class MuxBalancer(
  config: WhiskConfig,
  controllerInstance: ControllerInstanceId,
  feedFactory: FeedFactory,
  implicit val messagingProvider: MessagingProvider = SpiLoader.get[MessagingProvider])(
  implicit actorSystem: ActorSystem,
  logging: Logging)
    extends CommonLoadBalancer(config, feedFactory, controllerInstance) {

  private val defaultLoadBalancer =
    getClass[LoadBalancerProvider](lbConfig.activationStrategy.default).instance(config, controllerInstance)

  /**
   * Instantiates an object of the given type.
   *
   * Similar to SpiLoader.get, with the difference that the constructed class does not need to be declared as Spi.
   * Thus there could be multiple classes implementing same interface constructed at the same time
   *
   * @param name the name of the class
   * @tparam A expected type to return
   * @return instance of the class
   */
  private def getClass[A](name: String): A = {
    val clazz = Class.forName(name + "$")
    val classInst = clazz.getField("MODULE$").get(clazz).asInstanceOf[A]
    classInst
  }

  override def invokerHealth(): Future[IndexedSeq[InvokerHealth]] = Future.successful(IndexedSeq.empty[InvokerHealth])
  override protected def releaseInvoker(invoker: InvokerInstanceId, entry: ActivationEntry) = {
    // Currently do nothing
  }
  override protected val invokerPool: ActorRef = actorSystem.actorOf(Props.empty)

  /**
   * Publish a message to the loadbalancer
   *
   * Select the LoadBalancer based on the annotation, if available, otherwise use the default one
    **/
  override def publish(action: ExecutableWhiskActionMetaData, msg: ActivationMessage)(
    implicit transid: TransactionId): Future[Future[Either[ActivationId, WhiskActivation]]] = {
      defaultLoadBalancer.publish(action, msg)
  }
}

object MuxBalancer extends LoadBalancerProvider {

  override def instance(whiskConfig: WhiskConfig, instance: ControllerInstanceId)(
    implicit actorSystem: ActorSystem,
    logging: Logging): LoadBalancer = {

    new MuxBalancer(whiskConfig, instance, createFeedFactory(whiskConfig, instance))
  }
  def requiredProperties: Map[String, String] = kafkaHosts
  // def requiredProperties =
  //   ExecManifest.requiredProperties ++
  //     wskApiHost
}