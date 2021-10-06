package org.apache.openwhisk.common
import spray.json.DefaultJsonProtocol

case class RedisPacket (
  priorities: List[(String, Double, Double)], 
  containerActiveMem: Double, 
  usedMem: Double, 
  running: Double, 
  runningAndQ: Double, 
  cpuLoad: Double,
  loadAvg: Double)

object RedisPacketProtocol extends DefaultJsonProtocol {
  implicit val redisPacketFormat = jsonFormat7(RedisPacket.apply)
}