#!/usr/bin/env python3
"""
景枫中心停车场 MCP 服务器

功能：
1. 空余车位查询 - 定时从MySQL同步数据，支持按楼层/区域查询空余车位
2. 车牌落位查询 - 根据车牌号查找车辆位置
3. 路线推荐 - 推荐电梯或通道等路线
"""

import json
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# 初始化 MCP 服务器
mcp = FastMCP("jingfeng_parking_mcp")

# ============== 枚举定义 ==============

class FloorEnum(str, Enum):
    """楼层枚举"""
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    B4 = "B4"

class ResponseFormat(str, Enum):
    """输出格式"""
    MARKDOWN = "markdown"
    JSON = "json"

# ============== 数据模型 ==============

class ParkingSpace(BaseModel):
    """车位信息模型"""
    space_id: str = Field(..., description="车位编号，如 A001")
    floor: str = Field(..., description="楼层，如 B1, B2, B3, B4")
    area: str = Field(..., description="区域，如 A, B, C, D, E, F")
    status: str = Field(..., description="状态：available(空余), occupied(已占用), reserved(预留)")
    space_type: Optional[str] = Field(None, description="车位类型：standard(标准), ev(新能源), disabled(残疾人)")

class CarLocation(BaseModel):
    """车辆位置模型"""
    space_id: str = Field(..., description="车位编号")
    floor: str = Field(..., description="楼层")
    area: str = Field(..., description="区域")
    entrance: Optional[str] = Field(None, description="最近的入口")

class RouteRecommendation(BaseModel):
    """路线推荐模型"""
    destination: str = Field(..., description="目的地")
    recommended_route: str = Field(..., description="推荐路线")
    elevator: Optional[str] = Field(None, description="最近的电梯")
    passage: Optional[str] = Field(None, description="最近的通道")
    distance: Optional[str] = Field(None, description="距离")

# ============== 数据存储（内存缓存）==============

class ParkingDataStore:
    """停车数据存储 - 从MySQL同步的数据"""

    def __init__(self):
        self.parking_spaces: Dict[str, ParkingSpace] = {}
        self.car_locations: Dict[str, CarLocation] = {}
        self.last_sync_time: Optional[str] = None

    def get_available_spaces(self, floor: Optional[str] = None, area: Optional[str] = None) -> List[ParkingSpace]:
        """获取空余车位"""
        available = [s for s in self.parking_spaces.values() if s.status == "available"]
        if floor:
            available = [s for s in available if s.floor == floor]
        if area:
            available = [s for s in available if s.area == area]
        return available

    def get_car_location(self, license_plate: str) -> Optional[CarLocation]:
        """根据车牌查找车辆位置"""
        return self.car_locations.get(license_plate.upper().replace(" ", ""))

    def update_from_mysql(self, spaces: List[Dict], cars: List[Dict]):
        """从MySQL更新数据"""
        self.parking_spaces.clear()
        self.car_locations.clear()

        for s in spaces:
            space = ParkingSpace(**s)
            self.parking_spaces[space.space_id] = space

        for c in cars:
            location = CarLocation(**c)
            # 使用车牌作为key（去空格大写）
            key = c.get("license_plate", "").upper().replace(" ", "")
            self.car_locations[key] = location

        from datetime import datetime
        self.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 全局数据存储实例
data_store = ParkingDataStore()

# ============== 输入模型 ==============

class AvailableSpacesInput(BaseModel):
    """空余车位查询输入"""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    floor: Optional[FloorEnum] = Field(None, description="楼层：B1, B2, B3, B4")
    area: Optional[str] = Field(None, description="区域：如 A, B, C, D, E, F")
    limit: Optional[int] = Field(default=50, description="最大返回数量", ge=1, le=200)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="输出格式")

class CarLocationInput(BaseModel):
    """车牌落位查询输入"""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    license_plate: str = Field(..., description="车牌号，如 苏A12345", min_length=5, max_length=20)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="输出格式")

    @field_validator('license_plate')
    @classmethod
    def normalize_plate(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "")

class RouteRecommendationInput(BaseModel):
    """路线推荐输入"""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    destination: str = Field(..., description="目的地楼层或区域，如 B1, F1, 餐厅, 电影院")
    current_floor: Optional[str] = Field(None, description="当前所在楼层")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="输出格式")

class ParkingStatsInput(BaseModel):
    """停车场统计输入"""
    model_config = ConfigDict(str_strip_whitespace=True)

    floor: Optional[FloorEnum] = Field(None, description="楼层")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="输出格式")

# ============== 辅助函数 ==============

def _format_available_spaces(spaces: List[ParkingSpace], total: int, format: ResponseFormat) -> str:
    """格式化空余车位查询结果"""
    if not spaces:
        return "当前没有空余车位"

    if format == ResponseFormat.JSON:
        return json.dumps({
            "total_available": total,
            "count": len(spaces),
            "spaces": [s.model_dump() for s in spaces]
        }, indent=2, ensure_ascii=False)

    # Markdown 格式
    lines = ["# 空余车位查询结果", ""]
    lines.append(f"**总空余数量**: {total} 个")
    lines.append("")

    # 按楼层分组
    by_floor: Dict[str, List[ParkingSpace]] = {}
    for s in spaces:
        if s.floor not in by_floor:
            by_floor[s.floor] = []
        by_floor[s.floor].append(s)

    for floor in sorted(by_floor.keys()):
        floor_spaces = by_floor[floor]
        lines.append(f"## {floor} 层 ({len(floor_spaces)} 个)")
        for s in floor_spaces:
            type_emoji = {"ev": "⚡", "disabled": "♿", "standard": "🚗"}.get(s.space_type or "", "🚗")
            lines.append(f"- {type_emoji} **{s.space_id}** ({s.area}区) - {s.space_type or '标准'}")

        lines.append("")

    return "\n".join(lines)

def _get_route_for_location(location: CarLocation) -> str:
    """根据车位位置生成路线推荐"""

    # B2-B4层区域电梯映射（按实际数据）
    floor_area_elevators = {
        "B2": {
            "A": "B2层A电梯间或B电梯间直梯，或者写字楼办公电梯（可到达1楼）",
            "B": "B2层D电梯间直梯（到达再地西1楼），B2层A、B电梯间直梯，或者写字楼办公电梯（可到达1楼）",
            "C": "B2层C电梯间，或者写字楼办公电梯（可到达1楼）",
        },
        "B3": {
            "A": "B3层A电梯间或B电梯间直梯，或者写字楼办公电梯（可到达1楼）",
            "D": "B3层A电梯间或B电梯间直梯，或者写字楼办公电梯（可到达1楼）",
            "E": "B3层D电梯间直梯（到达再地西1楼），B3层A、B电梯间直梯，或者写字楼办公电梯（可到达1楼）",
            "F": "B3层C电梯间，或者写字楼办公电梯（可到达1楼），再地专用电梯",
        },
        "B4": {
            "0": "B4层C电梯间，或者写字楼办公电梯（可到达1楼）",
            "1": "B4层B电梯间，或者写字楼办公电梯（可到达1楼）",
            "2": "B4层B电梯间，或者写字楼办公电梯（可到达1楼）",
            "3": "B4层C电梯间，或者写字楼办公电梯（可到达1楼）",
        },
    }

    floor = location.floor
    area = location.area

    lines = []
    lines.append("")
    lines.append("## 🚗 智能路线推荐")

    # 检查是否有预定义的电梯推荐
    elevator_info = None
    if floor in floor_area_elevators and area in floor_area_elevators[floor]:
        elevator_info = floor_area_elevators[floor][area]
    elif floor.startswith("B"):
        elevator_info = f"{floor}层就近电梯间直梯，或者写字楼办公电梯（可到达1楼）"
    else:
        elevator_info = f"{floor}层就近电梯间，或者写字楼办公电梯"

    lines.append(f"**目标车位**: {location.space_id}（{location.area}区）")
    lines.append(f"**就近电梯间**: {elevator_info}")

    return "\n".join(lines)

def _format_car_location(location: Optional[CarLocation], plate: str, format: ResponseFormat) -> str:
    """格式化车辆位置查询结果"""
    if not location:
        return f"**未找到**车牌号 `{plate}` 的车辆\n\n可能原因：\n- 车辆不在场内\n- 车牌输入有误\n- 数据同步延迟"

    if format == ResponseFormat.JSON:
        return json.dumps({
            "license_plate": plate,
            "location": location.model_dump(),
            "route_recommendation": _get_route_for_location(location)
        }, indent=2, ensure_ascii=False)

    lines = [f"# 🔍 车牌落位查询结果: `{plate}`", ""]
    lines.append("---")
    lines.append("")
    lines.append("## 📍 位置信息")
    lines.append(f"- **车位编号**: `{location.space_id}`")
    lines.append(f"- **所在楼层**: **{location.floor}层**")
    lines.append(f"- **所在区域**: **{location.area}区**")

    # 自动带出路线推荐
    lines.append(_get_route_for_location(location))

    lines.append("")
    lines.append("---")
    lines.append("**温馨提示**: 如需帮助，请联系停车场工作人员或拨打客服热线 025-86155999")

    return "\n".join(lines)

def _format_route_recommendation(dest: str, format: ResponseFormat) -> str:
    """格式化路线推荐结果"""
    # 预定义的路线推荐
    route_map = {
        # 楼层间移动
        "B1": {"elevator": "A号电梯厅", "passage": "B1层主通道", "description": "从B1层东侧入口进入"},
        "B2": {"elevator": "B号电梯厅", "passage": "B2层主通道", "description": "从负二层电梯厅直达"},
        "B3": {"elevator": "C号电梯厅", "passage": "B3层主通道", "description": "从负三层电梯厅直达"},
        "B4": {"elevator": "D号电梯厅", "passage": "B4层主通道", "description": "从负四层电梯厅直达"},
        "F1": {"elevator": "A号电梯厅", "passage": "1层主通道", "description": "从一层电梯厅直达"},
        "F2": {"elevator": "B号电梯厅", "passage": "2层主通道", "description": "从二层电梯厅直达"},
        "F3": {"elevator": "C号电梯厅", "passage": "3层主通道", "description": "从三层电梯厅直达"},
        "F4": {"elevator": "D号电梯厅", "passage": "4层主通道", "description": "从四层电梯厅直达"},
    }

    # 特殊目的地
    special_routes = {
        "餐厅": {"floor": "B1/F4", "elevator": "就近电梯厅", "passage": "餐饮区通道", "description": "餐饮区分布在B1和F4层"},
        "电影院": {"floor": "F3", "elevator": "C号电梯厅", "passage": "3层电影院通道", "description": "CGV电影院位于3层"},
        "超市": {"floor": "B1", "elevator": "A号电梯厅", "passage": "B1层超市通道", "description": "永辉超市位于B1层"},
        "客户满意中心": {"floor": "F1", "elevator": "A号电梯厅", "passage": "1层主通道", "description": "客服中心位于1层施华洛世奇旁"},
    }

    route = route_map.get(dest.upper())
    special = special_routes.get(dest)

    if not route and not special:
        # 尝试匹配楼层
        for key in route_map:
            if key in dest.upper():
                route = route_map[key]
                break

    if not route and not special:
        return f"## 路线推荐\n\n抱歉，暂未找到前往「{dest}」的路线规划。\n\n建议您：\n- 联系现场工作人中的\n- 拨打客服热线 025-86155999 咨询"

    info = special if special else route

    if format == ResponseFormat.JSON:
        return json.dumps({
            "destination": dest,
            "route": info
        }, indent=2, ensure_ascii=False)

    lines = [f"# 路线推荐: 前往「{dest}」", ""]
    lines.append(f"**目标楼层**: {info.get('floor', '请咨询')}")
    lines.append(f"**推荐电梯**: {info.get('elevator', '')}")
    lines.append(f"**通道路线**: {info.get('passage', '')}")
    lines.append(f"**说明**: {info.get('description', '')}")
    lines.append("")
    lines.append("---")
    lines.append("**温馨提示**: 如需现场指引，请联系停车场工作人员或拨打客服热线 025-86155999")

    return "\n".join(lines)

def _format_parking_stats(format: ResponseFormat) -> str:
    """格式化停车场统计"""
    total = len(data_store.parking_spaces)
    available = len([s for s in data_store.parking_spaces.values() if s.status == "available"])
    occupied = total - available

    # 按楼层统计
    by_floor = {}
    for s in data_store.parking_spaces.values():
        if s.floor not in by_floor:
            by_floor[s.floor] = {"total": 0, "available": 0}
        by_floor[s.floor]["total"] += 1
        if s.status == "available":
            by_floor[s.floor]["available"] += 1

    if format == ResponseFormat.JSON:
        return json.dumps({
            "total_spaces": total,
            "available_spaces": available,
            "occupied_spaces": occupied,
            "occupancy_rate": f"{(occupied/total*100):.1f}%" if total > 0 else "0%",
            "last_sync_time": data_store.last_sync_time,
            "by_floor": by_floor
        }, indent=2, ensure_ascii=False)

    lines = ["# 景枫中心停车场实时状态", ""]
    lines.append(f"**总车位**: {total} 个")
    lines.append(f"**空余车位**: {available} 个")
    lines.append(f"**已占用**: {occupied} 个")
    occupancy_rate = (occupied / total * 100) if total > 0 else 0
    lines.append(f"**占用率**: {occupancy_rate:.1f}%")
    lines.append(f"**数据更新时间**: {data_store.last_sync_time or '暂无'}")
    lines.append("")
    lines.append("## 各楼层空余情况")

    for floor in ["B4", "B3", "B2", "B1"]:
        if floor in by_floor:
            stats = by_floor[floor]
            rate = (stats["total"] - stats["available"]) / stats["total"] * 100 if stats["total"] > 0 else 0
            lines.append(f"- **{floor}层**: {stats['available']}/{stats['total']} 空余 (占用率 {rate:.1f}%)")

    lines.append("")
    lines.append("---")
    lines.append("数据每5分钟自动同步，如需实时帮助请联系 025-86155999")

    return "\n".join(lines)

# ============== MCP Tools ==============

@mcp.tool(
    name="jingfeng_get_available_spaces",
    annotations={
        "title": "查询空余车位",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_available_spaces(params: AvailableSpacesInput) -> str:
    """
    查询景枫中心停车场空余车位

    支持按楼层和区域筛选，返回当前可用的停车位信息。

    Args:
        params (AvailableSpacesInput): 查询参数，包含：
            - floor (Optional[str]): 楼层 B1/B2/B3/B4
            - area (Optional[str]): 区域 A/B/C/D/E/F
            - limit (Optional[int]): 最大返回数量，默认50
            - response_format (str): 输出格式 markdown/json

    Returns:
        str: 空余车位列表，支持 markdown 和 json 格式
    """
    # 如果数据未初始化，先同步
    if not data_store.parking_spaces:
        sync_from_mysql()

    spaces = data_store.get_available_spaces(
        floor=params.floor.value if params.floor else None,
        area=params.area
    )

    return _format_available_spaces(spaces[:params.limit], len(spaces), params.response_format)

@mcp.tool(
    name="jingfeng_find_car_location",
    annotations={
        "title": "查询车牌落位",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def find_car_location(params: CarLocationInput) -> str:
    """
    根据车牌号查询车辆停放位置

    输入车牌号，返回车辆所在的车位编号和位置信息。

    Args:
        params (CarLocationInput): 查询参数，包含：
            - license_plate (str): 车牌号，如 苏A12345
            - response_format (str): 输出格式 markdown/json

    Returns:
        str: 车辆位置信息
    """
    if not data_store.parking_spaces:
        sync_from_mysql()

    location = data_store.get_car_location(params.license_plate)
    return _format_car_location(location, params.license_plate, params.response_format)

@mcp.tool(
    name="jingfeng_route_recommendation",
    annotations={
        "title": "路线推荐",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def route_recommendation(params: RouteRecommendationInput) -> str:
    """
    推荐前往目的地电梯或通道路线

    输入目的地楼层或区域，返回推荐的电梯和通道路线。

    Args:
        params (RouteRecommendationInput): 推荐参数，包含：
            - destination (str): 目的地楼层或区域，如 B1/F1/餐厅/电影院
            - current_floor (Optional[str]): 当前楼层
            - response_format (str): 输出格式 markdown/json

    Returns:
        str: 路线推荐信息
    """
    return _format_route_recommendation(params.destination, params.response_format)

@mcp.tool(
    name="jingfeng_parking_stats",
    annotations={
        "title": "停车场统计",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def parking_stats(params: ParkingStatsInput) -> str:
    """
    获取停车场实时统计数据

    返回当前总车位、空余车位、各楼层占用率等信息。

    Args:
        params (ParkingStatsInput): 统计参数，包含：
            - floor (Optional[str]): 可指定楼层
            - response_format (str): 输出格式 markdown/json

    Returns:
        str: 停车场统计数据
    """
    if not data_store.parking_spaces:
        sync_from_mysql()

    return _format_parking_stats(params.response_format)

# ============== 数据同步模块 ==============

def sync_from_mysql():
    """
    从MySQL数据库同步停车数据

    实际部署时需要替换为真实的MySQL连接和数据查询
    这里使用模拟数据作为示例
    """
    # TODO: 替换为真实的MySQL连接
    # import pymysql
    # conn = pymysql.connect(host='localhost', user='root', password='xxx', database='parking')
    #
    # # 查询车位数据
    # cursor.execute("SELECT space_id, floor, area, status, space_type FROM parking_spaces")
    # spaces = cursor.fetchall()
    #
    # # 查询车辆位置
    # cursor.execute("SELECT license_plate, space_id FROM cars WHERE status='parked'")
    # cars = cursor.fetchall()

    # 模拟数据（实际部署时从MySQL查询）
    import random

    floors = ["B1", "B2", "B3", "B4"]
    areas = ["A", "B", "C", "D", "E", "F"]
    space_types = ["standard", "ev", "disabled"]

    # 生成模拟车位数据
    spaces_data = []
    for floor in floors:
        for area in areas:
            for i in range(1, 41):  # 每区域约40个车位
                space_id = f"{area}{i:02d}"
                status = random.choice(["available", "occupied", "occupied", "occupied"])  # 约25%空余
                space_type = random.choice(space_types)
                spaces_data.append({
                    "space_id": space_id,
                    "floor": floor,
                    "area": area,
                    "status": status,
                    "space_type": space_type
                })

    # 生成模拟车辆数据
    cars_data = []
    for s in spaces_data:
        if s["status"] == "occupied":
            cars_data.append({
                "license_plate": f"苏A{random.randint(10000, 99999)}",
                "space_id": s["space_id"],
                "floor": s["floor"],
                "area": s["area"],
                "entrance": random.choice(["佳湖东路", "双龙大道"])
            })

    data_store.update_from_mysql(spaces_data, cars_data)

# ============== 定时同步任务 ==============

def start_periodic_sync(interval_minutes: int = 5):
    """启动定时同步任务"""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(sync_from_mysql, 'interval', minutes=interval_minutes)
    scheduler.start()
    return scheduler

# ============== 服务器入口 ==============

if __name__ == "__main__":
    import sys

    # 启动时先同步一次数据
    sync_from_mysql()

    # 启动定时同步任务（5分钟同步一次）
    scheduler = start_periodic_sync(5)

    # 根据参数选择传输方式
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        # Streamable HTTP 模式（用于远程部署）
        mcp.run(transport="streamable_http", port=8000)
    else:
        # stdio 模式（用于本地集成）
        mcp.run()