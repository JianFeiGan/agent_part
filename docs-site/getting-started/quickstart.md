# 5分钟上手

## 1. 启动服务

```bash
uv run python main.py
```

## 2. 创建商品

```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "智能运动手表",
    "category": "digital",
    "description": "支持心率监测、睡眠追踪的智能手表"
  }'
```

## 3. 创建生成任务

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "prod_001",
    "task_type": "image_and_video",
    "platform": "amazon"
  }'
```

## 4. 查看任务状态

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

## 下一步

- 了解 [系统架构](../concepts/architecture.md)
