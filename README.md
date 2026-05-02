# Proxium
Packet capturing tool based on port forwarding
# 什么是Proxium
Proxium是一款抓包工具，主要用于研究联机游戏比如Minecraft等游戏的数据包结构，Proxium作为端口转发，将转发过程中的数据包记录下来，并且可以在抓包页面导出为txt，由于Proxium导出的抓包记录是txt格式，所以可以很轻松的使用ai对数据包格式进行研究
# 教程
- ## 要求
  - Python 3.x
  - Tkinter（通常已随Python标准库安装）
  - 标准库：`socket`、`threading`、`tkinter`
- ## 运行
  - 下载Proxium.py，使用`python Proxium.py`即可运行
- ## 使用
  - `本地IP`即被抓包软件需要连接的IP，默认127.0.0.1，端口建议是被抓包软件的默认端口，如Minecraft的`25565`
  - `目标IP`即被抓包客户端要连接的服务器IP，默认127.0.0.1，但是这个要是服务器的IP，比如59.54.180.54，端口即客户端要连接到服务器的端口，比如25565，这个视服务器情况而定
# 感谢
Proxium使用了Lance-He开发的Port-Forwarder，在此感谢Lance-He的Port-Forwarder项目

[Lance-He/Port-Forwarder](https://github.com/Lance-He/Port-Forwarder/tree/main)
# Thanks
Proxium uses the Port-Forwarder developed by Lance-He, and we would like to thank Lance-He for the Port-Forwarder project

[Lance-He/Port-Forwarder](https://github.com/Lance-He/Port-Forwarder/tree/main)
