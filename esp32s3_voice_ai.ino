/**
 * ==============================================================================================
 *   ESP32-S3 AI BOOK READER - TRỢ LÝ GIỌNG NÓI THỜI GIAN THỰC (WEBSOCKET STREAMING)
 * ==============================================================================================
 *   Board:       ESP32S3 Dev Module
 *   Microphone:  INMP441 (I2S_NUM_0, 16kHz 16-bit Mono)
 *   Speaker DAC: MAX98357A (I2S_NUM_1, 44.1kHz 16-bit)
 *   Giao thức:   WebSocket Full-Duplex (Stream PCM Mic lên Server -> Nhận PCM Loa về phát ra)
 * ==============================================================================================
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>

// ===================== CẤU HÌNH WIFI & WEBSOCKET =====================
const char* WIFI_SSID     = "TEN_WIFI_CUA_BAN";
const char* WIFI_PASSWORD = "MAT_KHAU_WIFI";

// Đổi thành địa chỉ IPv4 của máy tính chạy backend FastAPI (xem bằng lệnh 'ipconfig' trên Windows)
const char* WS_HOST       = "192.168.1.145"; 
const int   WS_PORT       = 8000;

// Đường dẫn WebSocket (Có thể để "default" hoặc ID của cuốn sách bạn muốn tra cứu)
const char* WS_PATH       = "/api/ws/voice/default";

// ===================== CẤU HÌNH PHẦN CỨNG (PIN CONFIG) =====================
// 1. Microphone INMP441 (I2S0)
#define MIC_BCLK        5
#define MIC_WS          4
#define MIC_DIN         6
#define MIC_CHANNEL     I2S_CHANNEL_FMT_ONLY_LEFT
#define MIC_I2S_PORT    I2S_NUM_0
#define MIC_SAMPLE_RATE 16000

// 2. Speaker MAX98357A (I2S1)
#define SPK_BCLK        15
#define SPK_WS          16
#define SPK_DOUT        7
#define SPK_I2S_PORT    I2S_NUM_1
#define SPK_SAMPLE_RATE 44100

// 3. Nút bấm Push-to-Talk (Mặc định dùng nút BOOT GPIO 0 có sẵn trên ESP32-S3 Dev Module)
#define BUTTON_PIN      0

// Bộ đệm đọc âm thanh từ Mic (512 mẫu x 2 bytes = 1024 bytes mỗi frame)
#define MIC_BUFFER_SIZE 512
int16_t mic_buffer[MIC_BUFFER_SIZE];

WebSocketsClient webSocket;
bool isRecording = false;
bool isServerSpeaking = false;

// ===================== KHỞI TẠO I2S CHO MICROPHONE =====================
void setupMicrophone() {
  i2s_config_t mic_config = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate          = MIC_SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = MIC_CHANNEL,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = MIC_BUFFER_SIZE,
    .use_apll             = false,
    .tx_desc_auto_clear   = false,
    .fixed_mclk           = 0
  };

  i2s_pin_config_t mic_pins = {
    .bck_io_num   = MIC_BCLK,
    .ws_io_num    = MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = MIC_DIN
  };

  i2s_driver_install(MIC_I2S_PORT, &mic_config, 0, NULL);
  i2s_set_pin(MIC_I2S_PORT, &mic_pins);
  Serial.println("[I2S0] Microphone INMP441 đã sẵn sàng.");
}

// ===================== KHỞI TẠO I2S CHO LOA DAC =====================
void setupSpeaker() {
  i2s_config_t spk_config = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate          = SPK_SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = 512,
    .use_apll             = false,
    .tx_desc_auto_clear   = true, // Tự động xóa bộ đệm DMA tránh tiếng bụp khi dừng
    .fixed_mclk           = 0
  };

  i2s_pin_config_t spk_pins = {
    .bck_io_num   = SPK_BCLK,
    .ws_io_num    = SPK_WS,
    .data_out_num = SPK_DOUT,
    .data_in_num  = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(SPK_I2S_PORT, &spk_config, 0, NULL);
  i2s_set_pin(SPK_I2S_PORT, &spk_pins);
  Serial.println("[I2S1] Loa MAX98357A đã sẵn sàng.");
}

// ===================== XỬ LÝ SỰ KIỆN WEBSOCKET =====================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("\n[WS] Đã ngắt kết nối với máy chủ!");
      isServerSpeaking = false;
      break;

    case WStype_CONNECTED:
      Serial.printf("\n[WS] Đã kết nối thành công tới máy chủ: %s\n", payload);
      break;

    case WStype_TEXT: {
      StaticJsonDocument<1536> doc;
      DeserializationError error = deserializeJson(doc, payload);
      if (error) return;

      const char* status = doc["status"];
      const char* event  = doc["event"];

      if (status) {
        if (strcmp(status, "connected") == 0) {
          Serial.printf("[Hệ thống]: %s\n", doc["message"].as<const char*>());
        } else if (strcmp(status, "transcribing") == 0) {
          Serial.println("[AI]: Đang nhận diện giọng nói...");
        } else if (strcmp(status, "user_query") == 0) {
          Serial.printf("\n>>> [Bạn hỏi]: %s\n", doc["text"].as<const char*>());
        } else if (strcmp(status, "searching") == 0) {
          Serial.println("[AI]: Đang tìm kiếm trong sách...");
        } else if (strcmp(status, "answer") == 0) {
          Serial.printf("\n>>> [AI Trả lời]:\n%s\n\n", doc["text"].as<const char*>());
        } else if (strcmp(status, "synthesizing") == 0) {
          Serial.println("[AI]: Đang sinh giọng đọc...");
        } else if (strcmp(status, "error") == 0) {
          Serial.printf("[Lỗi]: %s\n", doc["message"].as<const char*>());
        }
      }

      if (event) {
        if (strcmp(event, "audio_start") == 0) {
          isServerSpeaking = true;
          Serial.println("[Audio]: Bắt đầu phát câu trả lời ra loa...");
        } else if (strcmp(event, "audio_end") == 0) {
          isServerSpeaking = false;
          Serial.println("[Audio]: Đã phát xong toàn bộ câu trả lời.");
        }
      }
      break;
    }

    // NHẬN DỮ LIỆU ÂM THANH RAW PCM (44.1kHz) TỪ SERVER VÀ GHI THẲNG RA LOA
    case WStype_BIN: {
      if (length > 0) {
        size_t bytes_written = 0;
        i2s_write(SPK_I2S_PORT, payload, length, &bytes_written, portMAX_DELAY);
      }
      break;
    }

    default:
      break;
  }
}

// ===================== SETUP =====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=======================================================");
  Serial.println("  ESP32-S3 TRỢ LÝ HỎI ĐÁP SÁCH GIÁO KHOA BẰNG GIỌNG NÓI  ");
  Serial.println("=======================================================");

  // Cấu hình nút bấm (nút BOOT GPIO 0 kéo lên nội bộ)
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Cấu hình I2S Mic & Loa
  setupMicrophone();
  setupSpeaker();

  // Kết nối WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Đang kết nối WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n-> WiFi đã kết nối! IP ESP32: " + WiFi.localIP().toString());

  // Kết nối WebSocket
  webSocket.begin(WS_HOST, WS_PORT, WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(3000);
  Serial.println("Hướng dẫn: BẤM VÀ GIỮ NÚT BOOT ĐỂ NÓI, THẢ RA ĐỂ NGHE TRẢ LỜI.");
}

// ===================== LOOP =====================
void loop() {
  webSocket.loop();

  // Đọc trạng thái nút bấm (LOW khi bấm, HIGH khi nhả)
  bool buttonPressed = (digitalRead(BUTTON_PIN) == LOW);

  // 1. Khi vừa bấm giữ nút: Bắt đầu thu âm
  if (buttonPressed && !isRecording && !isServerSpeaking) {
    isRecording = true;
    Serial.println("\n[Mic]: Bắt đầu thu âm (Đang giữ nút)...");
    webSocket.sendTXT("{\"event\":\"start\"}");
  }

  // 2. Trong lúc đang giữ nút: Đọc PCM từ Mic INMP441 và stream thẳng lên WebSocket
  if (buttonPressed && isRecording) {
    size_t bytes_read = 0;
    i2s_read(MIC_I2S_PORT, (char*)mic_buffer, sizeof(mic_buffer), &bytes_read, portMAX_DELAY);
    if (bytes_read > 0) {
      webSocket.sendBIN((uint8_t*)mic_buffer, bytes_read);
    }
  }

  // 3. Khi thả nút ra: Báo cho Server biết để bắt đầu xử lý AI
  if (!buttonPressed && isRecording) {
    isRecording = false;
    Serial.println("[Mic]: Đã thả nút. Chờ AI nhận diện và trả lời...");
    webSocket.sendTXT("{\"event\":\"stop\"}");
  }
}
