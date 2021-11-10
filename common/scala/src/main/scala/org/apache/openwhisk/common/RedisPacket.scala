package org.apache.openwhisk.common
import spray.json.DefaultJsonProtocol

case class RedisPacket (
  priorities: List[(String, Double, Double)], 
  containerActiveMem: Double, 
  usedMem: Double, 
  running: Double, 
  runningAndQ: Double, 
  cpuLoad: Double,
  loadAvg: Double,
  us: Int, // https://www.man7.org/linux/man-pages/man8/vmstat.8.html
  sy: Int,
  id: Int,
  wa: Int,
  st: Int)

object RedisPacketProtocol extends DefaultJsonProtocol {
  implicit val redisPacketFormat = jsonFormat12(RedisPacket.apply)
}