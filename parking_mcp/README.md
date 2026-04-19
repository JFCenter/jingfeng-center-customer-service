# 景枫中心停车场 MCP 服务器

基于 Model Context Protocol (MCP) 的停车场智能服务，支持空余车位查询、车牌落位查询、路线推荐等功能。

## 功能特性

### 1. 空余车位查询 (`jingfeng_get_available_spaces`)
- 支持按楼层筛选（B1/B2/B3/B4）
- 支持按区域筛选（A/B/C/D/E/F）
- 支持限制返回数量
- 支持 Markdown/JSON 两种输出格式

### 2. 车牌落位查询 (`jingfeng_find_car_location`)
- 根据车牌号查找车辆位置
- 返回车位编号和所在区域
- 提供找车路线指引

### 3. 路线推荐 (`jingfeng_route_recommendation`)
- 推荐最近的电梯
- 推荐通道路线
- 支持多种目的地（楼层、餐厅、电影院等）

### 4. 停车场统计 (`jingfeng_parking_stats`)
- 实时车位统计
- 各楼层占用率
- 数据更新时间

## 技术架构

```
                    ┌─────────────────┐
                    │   Claude AI     │
                    └────────┬────────┘
                             │ MCP Protocol
                    ┌────────▼────────┐
                    │ jingfeng_parking_mcp │
                    │   (FastMCP)     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │  tools    │  │ resources │  │  prompts  │
        │           │  │           │  │           │
        └───────────┘  └───────────┘  └───────────┘
                             │
                    ┌────────▼────────┐
                    │  数据存储层      │
                    │ (内存缓存+MySQL) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    MySQL        │
                    │   停车场数据库    │
                    └─────────────────┘
```

## 安装

```bash
cd jingfeng-center-customer-service/parking_mcp
pip install -r requirements.txt
```

## 配置

### 环境变量

```bash
export PARKING_DB_HOST="localhost"
export PARKING_DB_PORT="3306"
export PARKING_DB_USER="root"
export PARKING_DB_PASSWORD="your_password"
export PARKING_DB_NAME="parking"
```

## 使用方式

### 1. 初始化数据库

```bash
python src/init_db.py
```

### 2. 启动 MCP 服务器

**本地模式（stdio）：**
```bash
python src/server.py
```

**远程模式（HTTP）：**
```bash
python src/server.py --http
```

### 3. 手动同步数据

```bash
python src/sync.py
```

## 工具调用示例

### 查询空余车位

```python
# 请求
{
  "tool": "jingfeng_get_available_spaces",
  "params": {
    "floor": "B1",
    "area": "A",
    "limit": 20,
    "response_format": "markdown"
  }
}
```

### 查询车牌位置

```python
# 请求
{
  "tool": "jingfeng_find_car_location",
  "params": {
    "license_plate": "苏A12345",
    "response_format": "markdown"
  }
}
```

### 获取路线推荐

```python
# 请求
{
  "tool": "jingfeng_route_recommendation",
  "params": {
    "destination": "F3",
    "response_format": "markdown"
  }
}
```

## 数据库表结构

### parking_spaces（车位表）

| 字段 | 类型 | 说明 |
|------|------|------|
| space_id | VARCHAR(20) | 车位编号（如 A001） |
| floor | VARCHAR(10) | 楼层（B1/B2/B3/B4） |
| area | VARCHAR(10) | 区域（A/B/C/D/E/F） |
| status | ENUM | 状态：available/occupied/reserved |
| space_type | ENUM | 类型：standard/ev/disabled |

### car_locations（车辆位置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| license_plate | VARCHAR(20) | 车牌号 |
| space_id | VARCHAR(20) | 车位编号 |
| status | ENUM | 状态：parked/left |
| entrance | VARCHAR(50) | 最近入口 |

### parking_zones（区域信息表）

| 字段 | 类型 | 说明 |
|------|------|------|
| zone_name | VARCHAR(50) | 区域名称 |
| floor | VARCHAR(10) | 楼层 |
| nearest_elevator | VARCHAR(50) | 最近电梯 |
| nearest_entrance | VARCHAR(50) | 最近入口 |

## 与 Skill 集成

更新 `skill.json` 中的 MCP 配置：

```json
{
  "mcp": {
    "transport": "streamable-http",
    "endpoint": "http://localhost:8000/mcp",
    "tools": [
      "jingfeng_get_available_spaces",
      "jingfeng_find_car_location",
      "jingfeng_route_recommendation",
      "jingfeng_parking_stats"
    ]
  }
}
```

## 数据同步策略

- **启动时同步**：服务器启动时从 MySQL 加载数据
- **定时同步**：每 5 分钟自动从 MySQL 同步最新数据
- **手动同步**：可通过 `sync.py` 手动触发同步

## 扩展功能

后期可增加的功能：
1. 充电桩状态查询
2. 预约停车位
3. 停车费用计算
4. 反向寻车（输入车位找车）
5. 优惠活动查询

## 许可证

MIT