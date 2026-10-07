# mapchan

一个轻量的 Python 地图投影与 GPX 渲染工具。

`mapchan` 读取 GPX 轨迹，将 WGS84 经纬度转换到不同地图投影，并输出 SVG、PNG，
同时可以将所选投影的结果自动打包为 ZIP。

项目目前采用**单文件 Python 程序**设计，仅使用 Python 标准库，无需安装第三方依赖。

## Features

- 读取 GPX 文件
- 支持多个 `trkseg` / 多段轨迹
- 支持多种地图投影
- 输出 SVG
- 输出 PNG
- 将 SVG 与 PNG 自动打包为 ZIP
- 支持一次选择多个投影
- 仅使用 Python 标准库
- 无需 GIS 软件或额外 Python package

## Supported projections

### 1. Web Mercator

**Web Mercator / EPSG:3857**

适合与常见 Web 地图进行投影对照。

### 2. Equirectangular

**等距圆柱投影（Plate Carrée）**

一种简单直观的经纬度平面化方式，适合作为其他投影的对照基准。

### 3. Chinese 1963

**1963 年等差分纬线多圆锥投影**

中国地图制图中具有代表性的投影方案之一，主要用于中国视角的世界地图。

本项目采用：

- 中央经线：150°E

这里的 150°E 是世界地图版本的参数，而不是“中国全国地图”的中央经线。

### 4. Albers China

**Albers 等面积圆锥投影**

本项目提供一组用于中国全国尺度地图的参数：

- 中央经线：110°E
- 第一标准纬线：25°N
- 第二标准纬线：47°N

该参数组合主要用于全国尺度的地图投影与数据可视化。它作为本项目的默认“中国 Albers”配置，并不意味着所有中国地图或所有 GIS 数据都统一采用这一组参数。

## Requirements

- Python 3.x

仅使用 Python 标准库，不需要安装额外的 Python package。

## Usage

### Interactive mode

直接运行：

```bash
python mapchan.py example.gpx
```

程序会显示投影选择菜单，例如：

```text
[1] Web 墨卡托 (EPSG:3857)
[2] 等距圆柱
[3] 中国 1963 等差分纬线多圆锥投影
[4] 双标准纬线等积圆锥投影（中国）
[a] 全部生成
```

选择需要生成的投影即可。

支持一次选择多个投影，例如：

```text
1 4
```

### Command line mode

也可以直接通过参数指定投影：

```bash
python mapchan.py example.gpx --projection webmercator
```

选择多个投影：

```bash
python mapchan.py example.gpx --projection webmercator albers_china
```

生成全部投影：

```bash
python mapchan.py example.gpx --projection all
```

可用的投影名称：

```text
webmercator
equirectangular
chinese1963
albers_china
```

## Output

假设输入文件为：

```text
example.gpx
```

选择 Web Mercator 和 Albers 后，程序会生成：

```text
example.zip
```

ZIP 文件中直接包含各投影的 SVG 和 PNG：

```text
example_webmercator.svg
example_webmercator.png
example_albers_china.svg
example_albers_china.png
```

如果选择全部投影，则还会包含：

```text
example_equirectangular.svg
example_equirectangular.png
example_chinese1963.svg
example_chinese1963.png
```

ZIP 文件名默认使用原始 GPX 文件名：

```text
<原始文件名>.zip
```

例如：

```text
fuzhou.gpx
    ↓
fuzhou.zip
```

程序不会在文件名中加入时间戳或随机 ID。

## Getting GPX files

没有现成 GPX 文件时，可以从 GPS 设备、手机或户外/骑行服务中获取。

一些常见来源：

- [Wikiloc](https://www.wikiloc.com/) — 徒步、骑行及其他户外轨迹
- [Ride with GPS](https://ridewithgps.com/) — 骑行路线与活动记录
- [Komoot](https://www.komoot.com/) — 徒步、骑行和户外路线规划
- [OpenStreetMap GPS Traces](https://www.openstreetmap.org/traces) — 用户公开上传的 GPS 轨迹

最简单的测试方法通常是：

> 用手机、GPS 手表、骑行码表或其他 GPS 设备记录一段自己的步行或骑行轨迹，
> 再将其导出为 GPX。

使用第三方平台上的 GPX 文件时，请注意相关服务的使用条款，以及具体轨迹数据的授权和再分发限制。

## Why mapchan?

不同地图服务、地图资料和 GIS 数据可能采用不同的地图投影。

同一条 GPX 轨迹在不同投影下进行平面化后，其形状、位置和局部变形会有所不同。

`mapchan` 的主要目的，就是提供一个轻量、透明、容易修改的工具，让用户可以：

- 将 GPX 轨迹转换到不同投影
- 观察不同投影下的轨迹形状
- 对照不同地图资料的投影方式
- 快速生成 SVG / PNG 图形
- 在不依赖完整 GIS 软件的情况下进行基础投影实验

## Project scope

`mapchan` 当前主要面向：

- GPX 轨迹可视化
- 地图投影对照
- 轻量级制图实验
- SVG / PNG 图形输出

它**不是专业测绘软件，也不是完整 GIS 系统**。

对于高精度测绘、坐标转换、国家级测绘生产或严格要求与官方数据完全一致的场景，
应使用经过完整参数验证的专业 GIS / 测绘软件。

尤其需要注意：不同地图资料即使名称相同，也可能采用不同的参考椭球、基准、
参数或具体实现。使用投影时应以具体数据源的技术说明为准。

## Project structure

目前项目保持简单的单文件结构：

```text
mapchan/
├── mapchan.py
├── README.md
└── .gitignore
```

## Notes

本项目目前处于早期版本阶段。

投影模块与渲染模块保持相对独立，后续可以继续增加其他投影、
输入格式或地图数据处理能力，而不必改变基本的 GPX → 投影 → 平面坐标 → SVG/PNG
处理流程。
