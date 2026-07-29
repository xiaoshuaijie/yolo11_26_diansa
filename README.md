# E题

这个代码可以用在maixcam和maixcam2上, 注意models包含了maixcam和maixcam2的模型, 如果不需要可以自行删除

思路:
1. 使用yolo26检测小球
2. 固定maixcam到水管正上方, 固定水管, 计算小球在摄像头画面的像素位置, 反推出小球在水管上的位置

配置(可能没写全, 具体要自己看代码):

-  是否开启推流, 推荐同时只开启一个, 默认使用webrtc
USE_RTSP=False
USE_JPEG=False
USE_WEBRTC=True

- 输入打印. 关掉后提升帧率
DEBUG_LOG=True

- 畸变校准
LENS_CORR_ENABLE=False
LENS_CORR_STRENGTH=0.6


