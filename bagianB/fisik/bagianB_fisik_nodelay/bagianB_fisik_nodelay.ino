/*
 * Tugas Besar UTS IoT — Bagian B: HTTP vs MQTT QoS 0 vs MQTT QoS 1
 * Target: ESP32 FISIK + DHT11 di WiFi lab; broker & server HTTP berjalan di laptop (satu LAN)
 *
 * Skenario (masing-masing N_MSG pesan, jeda 2 s, timeout 5 s):
 *   S1 HTTP POST  ~20 B     S2 HTTP POST  ~500 B
 *   S3 MQTT QoS0  ~20 B     S4 MQTT QoS0  ~500 B
 *   S5 MQTT QoS1  ~20 B     S6 MQTT QoS1  ~500 B
 *
 * RTT diukur di perangkat yang sama (tanpa sinkronisasi jam):
 *   HTTP : request ditulis -> response lengkap diterima
 *   MQTT : publish -> pesan yang sama kembali dari broker (subscribe topik sendiri)
 * Pesan yang tidak kembali dalam 5 s dihitung hilang.
 *
 * Keputusan desain: HTTP memakai KEEP-ALIVE (koneksi TCP dipakai ulang)
 * agar setara dengan MQTT yang juga memakai satu koneksi TCP persisten.
 * Dengan begitu perbandingan mencerminkan overhead protokol aplikasi,
 * bukan biaya handshake TCP. Bila server menutup koneksi, perangkat
 * menyambung ulang dan baris log diberi reconn=1 (dibahas sebagai anomali).
 *
 * Sensor: DHT22 di GPIO4 (Wokwi hanya menyediakan DHT22; perangkat fisik memakai DHT11).
 * Setiap payload memuat bacaan suhu & kelembapan nyata dari sensor dengan lebar
 * tetap, lalu diisi 'x' sampai 20 B / 500 B persis -> ukuran payload tetap terkendali.
 *
 * Output Serial: baris "DATA,..." per pesan dan "SUM,..." per skenario.
 * Library: "MQTT" by Joel Gaehwiler (256dpi/arduino-mqtt) — mendukung publish QoS 1,
 *          "DHT sensor library" (Adafruit) — library yang sama dengan firmware Bagian A.
 */
#include <WiFi.h>
#include <MQTT.h>
#include <time.h>
#include <DHT.h>

// ================= KONFIGURASI =================
#define USE_WOKWI 0
#if USE_WOKWI
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";
#else
#include "secrets.h"   // WIFI_SSID, WIFI_PASS, SERVER_IP (laptop: broker + server HTTP lokal)
#endif

const char*    MQTT_HOST  = SERVER_IP;             // Mosquitto di laptop (satu LAN)
const uint16_t MQTT_PORT  = 1883;
const char*    HTTP_HOST  = SERVER_IP;             // server_lokal.py di laptop
const uint16_t HTTP_PORT  = 8080;
const char*    HTTP_PATH  = "/status/200";         // balasan 200 tanpa body

const int      N_MSG      = 100;     // pesan per skenario (syarat >= 100)
const uint32_t GAP_MS     = 2000;    // jeda antar-pesan
const uint32_t TIMEOUT_MS = 5000;    // batas dianggap hilang
const int      SIZE_SMALL = 20;
const int      SIZE_LARGE = 500;
const int      START_FROM = 0;      // 0=mulai S1; 4=lanjut dari S5 (jika run sebelumnya terhenti)
#define DHT_PIN 4
#if USE_WOKWI
#define DHT_MODEL DHT22
#else
#define DHT_MODEL DHT11
#endif
// ===============================================

struct Skenario { const char* id; const char* proto; int qos; int size; };
const Skenario SK[] = {
  {"S1", "http",  -1, SIZE_SMALL}, {"S2", "http",  -1, SIZE_LARGE},
  {"S3", "mqtt0",  0, SIZE_SMALL}, {"S4", "mqtt0",  0, SIZE_LARGE},
  {"S5", "mqtt1",  1, SIZE_SMALL}, {"S6", "mqtt1",  1, SIZE_LARGE},
};

WiFiClient netHttp, netMqtt;
MQTTClient mqtt(1024);
String topic;

volatile long     echoSeq = -1;   // seq terakhir yang kembali dari broker
volatile uint32_t echoUs  = 0;    // waktu kedatangannya (micros)
String curId;

float rtts[N_MSG];

DHT dht(DHT_PIN, DHT_MODEL);
float lastT = NAN, lastH = NAN;

void readSensor() {                      // dibaca SEBELUM timer RTT dimulai
  float h = dht.readHumidity(), t = dht.readTemperature();
  if (!isnan(h) && !isnan(t)) { lastT = t; lastH = h; }
}

// ---------- util ----------
String makePayload(const char* id, int seq, int size) {
  char head[32];
  // contoh: "S3,0042,24.0,40.0," (18 byte) -> header + bacaan sensor, lalu diisi 'x'
  snprintf(head, sizeof(head), "%s,%04d,%4.1f,%4.1f,", id, seq, lastT, lastH);
  String p(head);
  while ((int)p.length() < size) p += 'x';
  return p;
}

String nowStr() {
  struct tm ti;
  if (!getLocalTime(&ti, 200)) return "no-time";
  char b[20]; strftime(b, sizeof(b), "%Y-%m-%d %H:%M:%S", &ti);
  return String(b);
}

void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.println("# WiFi connecting...");
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);   // matikan modem-sleep: tanpa ini RTT melonjak sampai ratusan ms (sama seperti Bagian A)
#if USE_WOKWI
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
#else
  WiFi.begin(WIFI_SSID, WIFI_PASS);
#endif
  while (WiFi.status() != WL_CONNECTED) delay(100);
  Serial.printf("# WiFi OK, IP=%s RSSI=%d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

void summary(const char* id, int sent, int ok) {
  float s[N_MSG]; int n = 0;
  for (int i = 0; i < sent; i++) if (rtts[i] >= 0) s[n++] = rtts[i];
  if (n == 0) { Serial.printf("SUM,%s,%d,0,,,,\n", id, sent); return; }
  for (int i = 1; i < n; i++) { float k = s[i]; int j = i - 1; while (j >= 0 && s[j] > k) { s[j + 1] = s[j]; j--; } s[j + 1] = k; }
  double sum = 0; for (int i = 0; i < n; i++) sum += s[i];
  double mean = sum / n, var = 0; for (int i = 0; i < n; i++) var += (s[i] - mean) * (s[i] - mean);
  float med = (n % 2) ? s[n / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
  float p95 = s[(int)ceil(0.95 * n) - 1];
  Serial.printf("SUM,%s,%d,%d,%.2f,%.2f,%.2f,%.2f\n", id, sent, ok, mean, med, sqrt(var / n), p95);
}

// ---------- HTTP (raw socket supaya ukuran header terukur persis) ----------
int httpReconn = 0;

bool httpPost(const String& body, float& rttMs, int& reqB, int& respB, int& code, int& reconn) {
  reconn = 0;
  String req = String("POST ") + HTTP_PATH + " HTTP/1.1\r\n" +
               "Host: " + HTTP_HOST + "\r\n" +
               "User-Agent: G01-ESP32\r\n" +
               "Content-Type: text/plain\r\n" +
               "Content-Length: " + body.length() + "\r\n" +
               "Connection: keep-alive\r\n\r\n" + body;
  reqB = req.length();
  uint32_t t0 = micros();
  if (!netHttp.connected()) {               // koneksi putus -> handshake TCP ulang (ikut terhitung di RTT)
    netHttp.stop();
    reconn = 1; httpReconn++;
    if (!netHttp.connect(HTTP_HOST, HTTP_PORT)) { rttMs = -1; respB = 0; code = 0; return false; }
    netHttp.setNoDelay(true);               // TCP_NODELAY: matikan algoritma Nagle
  }
  netHttp.print(req);

  // baca status line + header sampai "\r\n\r\n"
  String hdr; int clen = 0; bool closeConn = false;
  uint32_t deadline = millis() + TIMEOUT_MS;
  while (millis() < deadline) {
    while (netHttp.available()) {
      char c = netHttp.read(); hdr += c;
      if (hdr.endsWith("\r\n\r\n")) goto header_done;
    }
    if (!netHttp.connected()) break;
    delay(1);
  }
  netHttp.stop(); rttMs = -1; respB = hdr.length(); code = 0; return false;

header_done:
  {
    code = hdr.substring(9, 12).toInt();
    String low = hdr; low.toLowerCase();
    int i = low.indexOf("content-length:");
    if (i >= 0) clen = low.substring(i + 15, low.indexOf("\r\n", i)).toInt();
    closeConn = low.indexOf("connection: close") >= 0;
    int got = 0;
    while (got < clen && millis() < deadline) { if (netHttp.available()) { netHttp.read(); got++; } else delay(1); }
    rttMs = (micros() - t0) / 1000.0f;
    respB = hdr.length() + got;
    if (closeConn) netHttp.stop();
    return got >= clen && code == 200;
  }
}

// ---------- MQTT ----------
void onMessage(String& t, String& payload) {
  if (!payload.startsWith(curId)) return;            // abaikan pesan skenario lain
  echoSeq = payload.substring(3, 7).toInt();
  echoUs  = micros();
}

int mqttReconn = 0;
int subQos = -1;

void ensureMqtt(int qos) {
  if (mqtt.connected() && subQos == qos) return;
  if (!mqtt.connected()) {
    String cid = "g01-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    while (!mqtt.connect(cid.c_str())) { Serial.printf("# MQTT connect gagal (err %d), ulang...\n", mqtt.lastError()); delay(1000); }
    mqttReconn++;
    netMqtt.setNoDelay(true);              // TCP_NODELAY: header & payload PUBLISH tidak ditahan Nagle
    subQos = -1;
  }
  if (subQos >= 0) mqtt.unsubscribe(topic);
  mqtt.subscribe(topic, qos);   // subscribe dengan QoS yang sama dengan publish
  subQos = qos;
  delay(300); mqtt.loop();
}

bool mqttSend(const String& p, int seq, int qos, float& rttMs, int& reconn) {
  int before = mqttReconn;
  ensureMqtt(qos);
  reconn = mqttReconn - before;
  echoSeq = -1;
  uint32_t t0 = micros();
  mqtt.publish(topic, p, false, qos);   // QoS1: menunggu PUBACK dari broker
  while ((long)echoSeq != seq && (micros() - t0) < TIMEOUT_MS * 1000UL) { mqtt.loop(); delay(1); }
  if ((long)echoSeq == seq) { rttMs = (echoUs - t0) / 1000.0f; return true; }
  rttMs = -1; return false;
}

// ---------- jalankan satu skenario ----------
void runSkenario(const Skenario& s) {
  curId = s.id;
  int ok = 0;
  Serial.printf("# %s mulai %s\n", s.id, nowStr().c_str());
  for (int seq = 1; seq <= N_MSG; seq++) {
    uint32_t tStart = millis();
    ensureWiFi();
    readSensor();
    String p = makePayload(s.id, seq, s.size);
    float rtt = -1; int reqB = 0, respB = 0, code = 0, reconn = 0; bool good;
    if (s.qos < 0) good = httpPost(p, rtt, reqB, respB, code, reconn);
    else           good = mqttSend(p, seq, s.qos, rtt, reconn);
    if (good) ok++;
    rtts[seq - 1] = good ? rtt : -1;
    // skenario,seq,payload_b,protokol,status,rtt_ms,req_b,resp_b,http_code,reconn,rssi_dbm,t_ms,suhu_c,rh
    Serial.printf("DATA,%s,%d,%d,%s,%s,%.3f,%d,%d,%d,%d,%d,%lu,%.1f,%.1f\n", s.id, seq, p.length(), s.proto,
                  good ? "ok" : "lost", rtt, reqB, respB, code, reconn, WiFi.RSSI(), millis(), lastT, lastH);
    while (millis() - tStart < GAP_MS) { if (mqtt.connected()) mqtt.loop(); delay(5); }
  }
  summary(s.id, N_MSG, ok);
  Serial.printf("# %s selesai %s\n", s.id, nowStr().c_str());
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  delay(500);
  ensureWiFi();
  configTime(7 * 3600, 0, "pool.ntp.org");
  topic = "g01syntech/rtt/" + String((uint32_t)ESP.getEfuseMac(), HEX);
  mqtt.begin(MQTT_HOST, MQTT_PORT, netMqtt);
  mqtt.onMessage(onMessage);
  mqtt.setOptions(30, true, TIMEOUT_MS);   // keepalive 30 s, clean session, timeout 5 s
  delay(1500);

  Serial.println("# ===== BAGIAN B G01 SYNTECH =====");
  Serial.printf("# waktu=%s wokwi=%d\n", nowStr().c_str(), USE_WOKWI);
  Serial.printf("# mqtt_broker=%s:%u topic=%s\n", MQTT_HOST, MQTT_PORT, topic.c_str());
  Serial.printf("# http_server=%s:%u%s keepalive=1\n", HTTP_HOST, HTTP_PORT, HTTP_PATH);
  Serial.printf("# n=%d gap_ms=%lu timeout_ms=%lu start_from=S%d\n", N_MSG, GAP_MS, TIMEOUT_MS, START_FROM + 1);
  Serial.printf("# sensor=%s pin=%d\n", USE_WOKWI ? "DHT22" : "DHT11", DHT_PIN);
  Serial.println("# tcp_nodelay=1");
  Serial.println("skenario,seq,payload_b,protokol,status,rtt_ms,req_b,resp_b,http_code,reconn,rssi_dbm,t_ms,suhu_c,rh");

  for (int i = START_FROM; i < 6; i++) runSkenario(SK[i]);

  Serial.printf("# SELESAI %s http_reconn=%d mqtt_reconn=%d\n", nowStr().c_str(), httpReconn, mqttReconn);
}

void loop() { if (mqtt.connected()) mqtt.loop(); delay(100); }
