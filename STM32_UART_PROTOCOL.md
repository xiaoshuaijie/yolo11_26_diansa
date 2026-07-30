# MaixPy 到 STM32 钢珠数据串口协议

MaixPy 端使用 `UART.write()` 发送原始字节流。两端配置为 `115200`、`8-N-1`，MaixCAM 的 TX 接 STM32 的 RX，MaixCAM 的 RX 接 STM32 的 TX，并且两端 GND 必须相连。两端都是 3.3 V 逻辑电平，不可把 5 V 信号直接接入 MaixCAM 或 STM32。

每次识别成功或丢失目标都会发送一个固定长度的 13 字节帧。所有多字节整数均为小端序。

| 字节偏移 | 长度 | 类型 | 含义 |
| --- | ---: | --- | --- |
| 0 | 1 | `uint8_t` | 帧头 `0xAA` |
| 1 | 1 | `uint8_t` | 帧头 `0x55` |
| 2 | 1 | `uint8_t` | `valid`：`1` 为检测有效，`0` 为钢珠丢失 |
| 3 | 2 | `int16_t` | `x_cm_x100`：位置（cm）乘以 100 |
| 5 | 2 | `int16_t` | `vx_px_s_x10`：速度（pixel/s）乘以 10 |
| 7 | 1 | `uint8_t` | `confidence_pct`：置信度百分比，范围 0 到 100 |
| 8 | 4 | `uint32_t` | `frame_time_ms`：MaixPy 毫秒时间戳 |
| 12 | 1 | `uint8_t` | 校验值：字节 0 至 11 的逐字节 XOR |

例如有效帧中的 `x_cm_x100 = 1234` 表示 `12.34 cm`，`vx_px_s_x10 = -567` 表示 `-56.7 pixel/s`。当 `valid == 0` 时，位置、速度和置信度均为 0；STM32 应忽略这些数值。

用 `valid=1`、`x_cm=12.34`、`vx_pixel_s=-56.7`、`confidence=0.88`、`frame_time_ms=12345678` 测试时，完整帧为：`AA 55 01 D2 04 C9 FD 58 4E 61 BC 00 D7`。最后的 `D7` 是前 12 个字节的 XOR 校验值。

下面的解析器可以放到 STM32 HAL 工程中。每收到一个字节都调用 `BallUart_PushByte()`；它会自动寻找帧头、校验数据，并在得到完整有效帧时调用 `BallUart_OnFrame()`。

```c
#include <stdbool.h>
#include <stdint.h>

#define BALL_FRAME_HEAD_0 0xAAU
#define BALL_FRAME_HEAD_1 0x55U
#define BALL_FRAME_LEN    13U

typedef struct {
    bool valid;
    int16_t x_cm_x100;
    int16_t vx_px_s_x10;
    uint8_t confidence_pct;
    uint32_t frame_time_ms;
} BallUartFrame;

static uint8_t BallUart_Checksum(const uint8_t *data, uint8_t length)
{
    uint8_t checksum = 0;

    for (uint8_t i = 0; i < length; ++i) {
        checksum ^= data[i];
    }
    return checksum;
}

static uint16_t ReadU16Le(const uint8_t *data)
{
    return (uint16_t)data[0] | ((uint16_t)data[1] << 8);
}

static uint32_t ReadU32Le(const uint8_t *data)
{
    return (uint32_t)data[0]
         | ((uint32_t)data[1] << 8)
         | ((uint32_t)data[2] << 16)
         | ((uint32_t)data[3] << 24);
}

static void BallUart_OnFrame(const BallUartFrame *frame)
{
    // 在此使用 frame：
    // float x_cm = frame->x_cm_x100 / 100.0f;
    // float vx_px_s = frame->vx_px_s_x10 / 10.0f;
}

void BallUart_PushByte(uint8_t byte)
{
    static uint8_t buffer[BALL_FRAME_LEN];
    static uint8_t index = 0;
    BallUartFrame frame;

    if (index == 0U) {
        if (byte == BALL_FRAME_HEAD_0) {
            buffer[index++] = byte;
        }
        return;
    }

    if (index == 1U) {
        if (byte == BALL_FRAME_HEAD_1) {
            buffer[index++] = byte;
        } else {
            index = (byte == BALL_FRAME_HEAD_0) ? 1U : 0U;
            if (index == 1U) {
                buffer[0] = byte;
            }
        }
        return;
    }

    buffer[index++] = byte;
    if (index != BALL_FRAME_LEN) {
        return;
    }

    index = 0;
    if (BallUart_Checksum(buffer, BALL_FRAME_LEN - 1U)
        != buffer[BALL_FRAME_LEN - 1U]) {
        return;
    }

    frame.valid = buffer[2] != 0U;
    frame.x_cm_x100 = (int16_t)ReadU16Le(&buffer[3]);
    frame.vx_px_s_x10 = (int16_t)ReadU16Le(&buffer[5]);
    frame.confidence_pct = buffer[7];
    frame.frame_time_ms = ReadU32Le(&buffer[8]);
    BallUart_OnFrame(&frame);
}
```

使用 HAL 的单字节中断接收时，可按下面方式连接解析器。`huart1` 应替换为实际连接 MaixCAM 的 UART 句柄。

```c
extern UART_HandleTypeDef huart1;
static uint8_t uart1_rx_byte;

void BallUart_Start(void)
{
    HAL_UART_Receive_IT(&huart1, &uart1_rx_byte, 1U);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart == &huart1) {
        BallUart_PushByte(uart1_rx_byte);
        HAL_UART_Receive_IT(&huart1, &uart1_rx_byte, 1U);
    }
}
```

若项目采用 DMA 空闲中断接收，则将本次收到的每个字节依次传给 `BallUart_PushByte()` 即可，不需要改变协议解析逻辑。
