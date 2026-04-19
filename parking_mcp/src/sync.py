#!/usr/bin/env python3
"""
停车数据同步脚本

从MySQL数据库同步停车数据到MCP服务器的内存存储
支持定时同步和手动触发同步
"""

import os
from datetime import datetime
from typing import List, Dict, Optional

import pymysql
from pymysql.cursors import DictCursor

# 数据库配置 - 从环境变量读取
DB_CONFIG = {
    "host": os.getenv("PARKING_DB_HOST", "localhost"),
    "port": int(os.getenv("PARKING_DB_PORT", "3306")),
    "user": os.getenv("PARKING_DB_USER", "root"),
    "password": os.getenv("PARKING_DB_PASSWORD", ""),
    "database": os.getenv("PARKING_DB_NAME", "parking"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor
}

class ParkingDataSyncer:
    """停车数据同步器"""

    def __init__(self, db_config: Optional[Dict] = None):
        self.db_config = db_config or DB_CONFIG
        self.last_sync_time: Optional[datetime] = None

    def connect(self) -> pymysql.Connection:
        """建立数据库连接"""
        return pymysql.connect(**self.db_config)

    def fetch_parking_spaces(self, conn: pymysql.Connection) -> List[Dict]:
        """
        获取车位数据

        Returns:
            List[Dict]: 车位列表，每条记录包含:
                - space_id: 车位编号
                - floor: 楼层
                - area: 区域
                - status: 状态 (available/occupied/reserved)
                - space_type: 车位类型 (standard/ev/disabled)
        """
        sql = """
            SELECT
                space_id,
                floor,
                area,
                status,
                space_type
            FROM parking_spaces
            WHERE status IN ('available', 'occupied', 'reserved')
            ORDER BY floor, area, space_id
        """
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def fetch_car_locations(self, conn: pymysql.Connection) -> List[Dict]:
        """
        获取车辆位置数据

        Returns:
            List[Dict]: 车辆位置列表，每条记录包含:
                - license_plate: 车牌号
                - space_id: 车位编号
                - floor: 楼层
                - area: 区域
                - entrance: 最近入口
        """
        sql = """
            SELECT
                license_plate,
                space_id,
                floor,
                area,
                entrance
            FROM car_locations cl
            INNER JOIN parking_spaces ps ON cl.space_id = ps.space_id
            WHERE cl.status = 'parked'
        """
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def sync(self) -> Dict[str, int]:
        """
        执行同步操作

        Returns:
            Dict: 同步统计信息
                - spaces_count: 车位数量
                - cars_count: 车辆数量
                - sync_time: 同步时间
        """
        try:
            conn = self.connect()

            # 获取车位数据
            spaces = self.fetch_parking_spaces(conn)

            # 获取车辆位置数据
            cars = self.fetch_car_locations(conn)

            conn.close()

            # 更新内存存储
            from server import data_store
            data_store.update_from_mysql(spaces, cars)

            self.last_sync_time = datetime.now()

            return {
                "spaces_count": len(spaces),
                "cars_count": len(cars),
                "sync_time": self.last_sync_time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success"
            }

        except pymysql.Error as e:
            return {
                "status": "error",
                "error": str(e),
                "sync_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

def main():
    """手动执行同步"""
    syncer = ParkingDataSyncer()
    result = syncer.sync()

    print(f"同步结果: {result}")

    if result["status"] == "success":
        print(f"成功同步 {result['spaces_count']} 个车位, {result['cars_count']} 辆车")
    else:
        print(f"同步失败: {result.get('error', '未知错误')}")
        exit(1)

if __name__ == "__main__":
    main()