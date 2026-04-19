#!/usr/bin/env python3
"""
MySQL数据库初始化脚本

创建停车场所需的数据库表结构
"""

import os

SQL_STATEMENTS = [
    # 创建车位表
    """
    CREATE TABLE IF NOT EXISTS parking_spaces (
        space_id VARCHAR(20) PRIMARY KEY COMMENT '车位编号，如 A001',
        floor VARCHAR(10) NOT NULL COMMENT '楼层：B1/B2/B3/B4',
        area VARCHAR(10) NOT NULL COMMENT '区域：A/B/C/D/E/F',
        status ENUM('available', 'occupied', 'reserved') DEFAULT 'available' COMMENT '状态：空余/已占用/预留',
        space_type ENUM('standard', 'ev', 'disabled') DEFAULT 'standard' COMMENT '车位类型：标准/新能源/残疾人',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_floor (floor),
        INDEX idx_status (status),
        INDEX idx_area (area)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='车位信息表';
    """,

    # 创建车辆位置表
    """
    CREATE TABLE IF NOT EXISTS car_locations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        license_plate VARCHAR(20) NOT NULL COMMENT '车牌号',
        space_id VARCHAR(20) NOT NULL COMMENT '车位编号',
        status ENUM('parked', 'left') DEFAULT 'parked' COMMENT '状态：在场/离场',
        entrance VARCHAR(50) COMMENT '最近的入口',
        parked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '停车时间',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_plate (license_plate),
        INDEX idx_space_id (space_id),
        INDEX idx_status (status),
        FOREIGN KEY (space_id) REFERENCES parking_spaces(space_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='车辆位置表';
    """,

    # 创建车位区域表（用于路线推荐）
    """
    CREATE TABLE IF NOT EXISTS parking_zones (
        id INT AUTO_INCREMENT PRIMARY KEY,
        zone_name VARCHAR(50) NOT NULL COMMENT '区域名称',
        floor VARCHAR(10) NOT NULL COMMENT '楼层',
        nearest_elevator VARCHAR(50) COMMENT '最近的电梯',
        nearest_entrance VARCHAR(50) COMMENT '最近的主入口',
        description VARCHAR(200) COMMENT '区域描述',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='停车区域信息表';
    """,

    # 插入示例数据
    """
    INSERT IGNORE INTO parking_zones (zone_name, floor, nearest_elevator, nearest_entrance, description) VALUES
    ('A区', 'B1', 'A号电梯厅', '佳湖东路入口', 'B1层东侧A区'),
    ('B区', 'B1', 'A号电梯厅', '佳湖东路入口', 'B1层东侧B区'),
    ('C区', 'B1', 'B号电梯厅', '双龙大道入口', 'B1层西侧C区'),
    ('A区', 'B2', 'B号电梯厅', '佳湖东路入口', 'B2层东侧A区'),
    ('B区', 'B2', 'B号电梯厅', '双龙大道入口', 'B2层东侧B区'),
    ('F区', 'B3', 'C号电梯厅', '佳湖东路入口', 'B3层西侧F区（新能源专区）'),
    ('A区', 'B3', 'C号电梯厅', '佳湖东路入口', 'B3层东侧A区'),
    ('A区', 'B4', 'D号电梯厅', '佳湖东路入口', 'B4层东侧A区');
    """,
]

def init_database():
    """初始化数据库表结构"""
    import pymysql

    # 连接数据库
    conn = pymysql.connect(
        host=os.getenv("PARKING_DB_HOST", "localhost"),
        port=int(os.getenv("PARKING_DB_PORT", "3306")),
        user=os.getenv("PARKING_DB_USER", "root"),
        password=os.getenv("PARKING_DB_PASSWORD", ""),
        charset="utf8mb4"
    )

    try:
        with conn.cursor() as cursor:
            # 创建数据库（如果不存在）
            cursor.execute("CREATE DATABASE IF NOT EXISTS parking CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cursor.execute("USE parking")

            # 执行建表语句
            for sql in SQL_STATEMENTS:
                cursor.execute(sql)

            conn.commit()
            print("数据库初始化成功!")

    finally:
        conn.close()

def init_sample_data():
    """初始化示例车位数据"""
    import random
    import pymysql

    conn = pymysql.connect(
        host=os.getenv("PARKING_DB_HOST", "localhost"),
        port=int(os.getenv("PARKING_DB_PORT", "3306")),
        user=os.getenv("PARKING_DB_USER", "root"),
        password=os.getenv("PARKING_DB_PASSWORD", ""),
        database="parking",
        charset="utf8mb4"
    )

    try:
        with conn.cursor() as cursor:
            # 检查是否已有数据
            cursor.execute("SELECT COUNT(*) FROM parking_spaces")
            count = cursor.fetchone()[0]

            if count > 0:
                print(f"车位表已有 {count} 条数据，跳过初始化")
                return

            # 生成车位数据
            floors = ["B1", "B2", "B3", "B4"]
            areas = ["A", "B", "C", "D", "E", "F"]
            space_types = ["standard", "ev", "disabled"]

            values = []
            for floor in floors:
                for area in areas:
                    for i in range(1, 41):
                        space_id = f"{area}{i:02d}"
                        status = random.choice(["available", "occupied", "occupied", "occupied"])
                        space_type = random.choice(space_types) if random.random() > 0.1 else "standard"
                        values.append(f"('{space_id}', '{floor}', '{area}', '{status}', '{space_type}')")

            sql = f"INSERT INTO parking_spaces (space_id, floor, area, status, space_type) VALUES {','.join(values)}"
            cursor.execute(sql)

            conn.commit()
            print(f"成功初始化 {len(values)} 个车位")

    finally:
        conn.close()

if __name__ == "__main__":
    init_database()
    init_sample_data()