/*
 * Tugas Besar UTS IoT — Bagian A
 * ESP32 + DHT11 -> WiFi -> ThingSpeak (HTTP REST), interval 30 detik
 *
 * Field ThingSpeak (beri nama + satuan di Channel Settings):
 *   field1 = Suhu (°C)
 *   field2 = Kelembapan (%RH)
 *   field3 = RSSI (dBm)
 *   field4 = Seq (nomor urut sampel)       -> deteksi sampel hilang
 *   field5 = Uptime (s)                     -> deteksi reboot (uptime reset)
 *   field6 = Error kirim kumulatif (count)
 *   field7 = Status sensor (1=OK, 0=gagal baca)
 *
 * Library: "DHT sensor library" (Adafruit) + "Adafruit Unified Sensor"
 * Board  : ESP32 Dev Module (Arduino core ESP32 v2.x atau v3.x)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <esp_task_wdt.h>
#include <time.h>
#include "secrets.h"   // WIFI_SSID, WIFI_PASS, TS_WRITE_KEY (tidak di-commit ke Git)

// ================== KONFIGURASI ==================
const char* TS_URL       = "http://api.thingspeak.com/update";   // port 80, tanpa TLS

#define DHT_PIN   4
#define DHT_TYPE  DHT11

const uint32_t SEND_INTERVAL_MS = 30000;  // 30 s (batas minimal ThingSpeak free = 15 s)
const uint32_t WDT_TIMEOUT_S    = 60;     // reboot otomatis jika program macet > 60 s
const uint8_t  HTTP_MAX_TRY     = 3;      // 1 kirim + 2 retry
const uint8_t  WIFI_FAIL_REBOOT = 10;     // 10 siklus gagal WiFi (~5 menit) -> restart
// =================================================

DHT dht(DHT_PIN, DHT_TYPE);

uint32_t seq            = 0;
uint32_t errCount       = 0;
uint32_t lastSend       = 0;
uint8_t  wifiFailStreak = 0;

// ---------- Watchdog: reboot jika loop macet ----------
void initWatchdog() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t cfg = {
    .timeout_ms     = WDT_TIMEOUT_S * 1000,
    .idle_core_mask = 0,
    .trigger_panic  = true
  };
  esp_task_wdt_reconfigure(&cfg);
#else
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
#endif
  esp_task_wdt_add(NULL);   // daftarkan task loop() ke watchdog
}

// ---------- WiFi dengan timeout ----------
bool connectWiFi(uint32_t timeoutMs = 20000) {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < timeoutMs) {
    delay(500);
    esp_task_wdt_reset();
  }
  return WiFi.status() == WL_CONNECTED;
}

// ---------- Baca DHT11 dengan retry ----------
bool readDHT(float &t, float &h) {
  for (uint8_t i = 0; i < 3; i++) {
    h = dht.readHumidity();
    t = dht.readTemperature();
    if (!isnan(h) && !isnan(t)) return true;
    delay(2100);              // DHT11 butuh jeda antar-pembacaan
    esp_task_wdt_reset();
  }
  return false;
}

// ---------- Kirim ke ThingSpeak ----------
// Return entry_id (>0) jika diterima, -1 jika gagal/ditolak
long sendThingSpeak(bool sensorOk, float t, float h) {
  String url = String(TS_URL) + "?api_key=" + TS_WRITE_KEY;
  if (sensorOk) {
    url += "&field1=" + String(t, 1);
    url += "&field2=" + String(h, 1);
  }                                        // gagal baca -> field1/2 kosong (jujur, bukan diisi rekaan)
  url += "&field3=" + String(WiFi.RSSI());
  url += "&field4=" + String(seq);
  url += "&field5=" + String(millis() / 1000);
  url += "&field6=" + String(errCount);
  url += "&field7=" + String(sensorOk ? 1 : 0);

  HTTPClient http;
  http.setTimeout(8000);
  http.begin(url);
  int code = http.GET();
  String body = (code > 0) ? http.getString() : "";
  http.end();

  // ThingSpeak membalas entry_id jika sukses, "0" jika ditolak (mis. terlalu cepat)
  long entry = body.toInt();
  return (code == 200 && entry > 0) ? entry : -1;
}

// ---------- Timestamp lokal (WIB) untuk Serial log ----------
String nowStr() {
  struct tm ti;
  if (!getLocalTime(&ti, 100)) return "no-time";
  char buf[20];
  strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &ti);
  return String(buf);
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);          // matikan modem sleep agar koneksi stabil
  WiFi.setAutoReconnect(true);

  initWatchdog();
  connectWiFi();
  configTime(7 * 3600, 0, "id.pool.ntp.org", "pool.ntp.org");   // UTC+7 (WIB)

  Serial.println("time,seq,temp_c,hum_pct,rssi_dbm,entry_id,err_count");
}

void loop() {
  esp_task_wdt_reset();

  // Jadwal berbasis millis(): interval tetap 30 s walau proses kirim memakan waktu
  if (lastSend != 0 && millis() - lastSend < SEND_INTERVAL_MS) {
    delay(100);
    return;
  }
  lastSend = millis();
  seq++;                          // seq tetap naik walau gagal kirim -> celah seq = sampel hilang

  float t = NAN, h = NAN;
  bool sensorOk = readDHT(t, h);

  if (!connectWiFi()) {
    errCount++;
    Serial.printf("%s,%lu,WIFI_FAIL\n", nowStr().c_str(), seq);
    if (++wifiFailStreak >= WIFI_FAIL_REBOOT) ESP.restart();
    return;
  }
  wifiFailStreak = 0;

  long entry = -1;
  for (uint8_t i = 0; i < HTTP_MAX_TRY && entry < 0; i++) {
    if (i > 0) delay(5000);
    esp_task_wdt_reset();
    entry = sendThingSpeak(sensorOk, t, h);
  }
  if (entry < 0) errCount++;

  Serial.printf("%s,%lu,%.1f,%.1f,%d,%ld,%lu\n",
                nowStr().c_str(), seq, t, h, WiFi.RSSI(), entry, errCount);
}
