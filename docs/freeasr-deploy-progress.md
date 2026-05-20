# FreeASR 服务器部署进度

## 服务器信息
- **IP**: 8.152.168.44
- **配置**: 2C2G（1.8GB 内存），40GB 磁盘，Alibaba Cloud Linux 3
- **SSH**: root / 密码登录
- **域名**: 已解析至该服务器

## 已完成

### 系统环境
- 2GB swap 已添加并持久化（`/etc/fstab`）
- Nginx 已安装并运行，静态页面在 `/var/www/freeasr/index.html`

### Python 环境
- Miniconda 安装于 `/opt/miniconda`
- conda 环境 `asr`（Python 3.10）已创建
- PyTorch 2.12.0+cpu 已安装
- FunASR 1.3.1 已安装
- modelscope 1.37.0 已安装

### 模型下载
- SenseVoiceSmall: `/opt/models/iic/SenseVoiceSmall/model.pt`
- VAD: `/opt/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch/model.pt`

### 测试脚本
- `/tmp/test_infer.py` — 无 VAD 的精简推理测试

## 阻塞问题

**2C2G 内存不足，推理时 OOM。** Python 进程加载模型后 ~1.5GB RSS，超过 1.8GB 物理内存，即使有 2GB swap 也会被内核 kill。

升级到 2C4G 即可直接跑。

## 下一步方向

1. 升级到 2C4G，直接跑 `/opt/miniconda/envs/asr/bin/python /tmp/test_infer.py`
2. 或者不走本地 ASR，改用阿里云智能语音交互 API（同账号内网访问，新用户 3 个月免费 500h/月）
