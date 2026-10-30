package ir.admin98.oltmonitor

import android.app.Activity
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.jcraft.jsch.ChannelShell
import com.jcraft.jsch.JSch
import com.jcraft.jsch.Session
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import kotlin.math.max

class MainActivity : Activity() {
    private val navy = Color.rgb(13, 31, 54)
    private val blue = Color.rgb(26, 113, 196)
    private val cyan = Color.rgb(30, 190, 200)
    private val ink = Color.rgb(31, 48, 67)
    private val muted = Color.rgb(111, 130, 149)
    private val worker = Executors.newSingleThreadScheduledExecutor()
    private val main = Handler(Looper.getMainLooper())
    private var pollTask: ScheduledFuture<*>? = null
    private var client: OltSshClient? = null
    @Volatile private var connected = false

    private lateinit var hostInput: EditText
    private lateinit var sshPortInput: EditText
    private lateinit var userInput: EditText
    private lateinit var passwordInput: EditText
    private lateinit var frameInput: EditText
    private lateinit var slotInput: EditText
    private lateinit var portInput: EditText
    private lateinit var cpuSlotInput: EditText
    private lateinit var intervalInput: EditText
    private lateinit var connectButton: Button
    private lateinit var statusText: TextView
    private lateinit var rxText: TextView
    private lateinit var txText: TextView
    private lateinit var rxPpsText: TextView
    private lateinit var txPpsText: TextView
    private lateinit var cpuText: TextView
    private lateinit var memText: TextView
    private lateinit var tempText: TextView
    private lateinit var fanText: TextView
    private lateinit var uplink8Text: TextView
    private lateinit var uplink9Text: TextView
    private lateinit var chart: TrafficChartView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = navy
        window.navigationBarColor = navy
        buildUi()
    }

    private fun buildUi() {
        val scroll = ScrollView(this).apply { setBackgroundColor(Color.rgb(242, 247, 251)) }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(18), dp(16), dp(24))
            layoutDirection = View.LAYOUT_DIRECTION_RTL
        }
        scroll.addView(root)
        setContentView(scroll)

        val header = card(navy)
        header.addView(label("OLT Monitor", 24, Color.WHITE, true))
        header.addView(label("مانیتورینگ زنده Huawei MA5683T", 14, Color.rgb(198, 220, 239)))
        header.addView(label("پایش ترافیک، منابع و وضعیت تجهیزات", 12, Color.rgb(160, 190, 216)))
        root.addView(header, matchWrap())

        root.addView(sectionTitle("تنظیمات اتصال"))
        val connectionCard = card(Color.WHITE)
        hostInput = field(connectionCard, "آدرس IP یا نام میزبان OLT", "192.168.1.100")
        val row1 = row(connectionCard)
        sshPortInput = field(row1, "پورت SSH", "22", true)
        userInput = field(row1, "نام کاربری", "admin")
        passwordInput = field(connectionCard, "رمز عبور SSH", "", false, true)
        root.addView(connectionCard, matchWrap())

        root.addView(sectionTitle("تنظیمات Interface"))
        val interfaceCard = card(Color.WHITE)
        val row2 = row(interfaceCard)
        frameInput = field(row2, "Frame", "0", true)
        slotInput = field(row2, "Slot", "8", true)
        portInput = field(row2, "Port", "0", true)
        val row3 = row(interfaceCard)
        cpuSlotInput = field(row3, "اسلات CPU / دما", "0/7")
        intervalInput = field(row3, "فاصله نمونه‌برداری (ثانیه)", "2", true)
        root.addView(interfaceCard, matchWrap())

        connectButton = Button(this).apply {
            text = "اتصال به OLT و شروع پایش"
            isAllCaps = false
            setTextColor(Color.WHITE)
            setBackground(round(blue, 14))
            setOnClickListener { toggleConnection() }
        }
        root.addView(connectButton, matchWrap(dp(54)))

        statusText = label("وضعیت: قطع", 13, muted)
        statusText.setPadding(dp(4), dp(10), dp(4), dp(8))
        root.addView(statusText)

        root.addView(sectionTitle("ترافیک لحظه‌ای"))
        val trafficCard = card(Color.WHITE)
        val metrics = row(trafficCard)
        rxText = metric(metrics, "دریافت RX", "— Kbit/s", cyan)
        txText = metric(metrics, "ارسال TX", "— Kbit/s", blue)
        val packets = row(trafficCard)
        rxPpsText = metric(packets, "RX Packets", "— pps", cyan)
        txPpsText = metric(packets, "TX Packets", "— pps", blue)
        chart = TrafficChartView(this)
        trafficCard.addView(chart, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(190)).apply {
            topMargin = dp(12)
        })
        trafficCard.addView(label("نمودار RX و TX · آخرین ۶۰ نمونه", 11, muted))
        root.addView(trafficCard, matchWrap())

        root.addView(sectionTitle("وضعیت دستگاه"))
        val systemCard = card(Color.WHITE)
        val systemRow1 = row(systemCard)
        cpuText = metric(systemRow1, "CPU", "—", blue)
        memText = metric(systemRow1, "Memory", "—", cyan)
        tempText = metric(systemCard, "Temperature", "—", Color.rgb(232, 145, 48))
        val systemRow2 = row(systemCard)
        fanText = metric(systemRow2, "FAN", "—", Color.rgb(34, 160, 110))
        uplink8Text = metric(systemRow2, "Uplink 0/8", "—", blue)
        uplink9Text = metric(systemRow2, "Uplink 0/9", "—", cyan)
        root.addView(systemCard, matchWrap())

        root.addView(label("اطلاعات اتصال فقط در همین نشست استفاده می‌شود و رمز عبور ذخیره نمی‌شود.", 11, muted))
    }

    private fun toggleConnection() {
        if (connected) {
            stopMonitoring()
            return
        }
        val host = hostInput.text.toString().trim()
        val user = userInput.text.toString().trim()
        val pass = passwordInput.text.toString()
        val sshPort = sshPortInput.text.toString().toIntOrNull() ?: 22
        if (host.isBlank() || user.isBlank() || pass.isBlank()) {
            statusText.text = "وضعیت: آدرس، نام کاربری و رمز عبور را وارد کنید."
            return
        }
        val frame = frameInput.text.toString().toIntOrNull() ?: 0
        val slot = slotInput.text.toString().toIntOrNull() ?: 8
        val port = portInput.text.toString().toIntOrNull() ?: 0
        val cpuSlot = cpuSlotInput.text.toString().trim().ifBlank { "0/7" }
        val interval = (intervalInput.text.toString().toIntOrNull() ?: 2).coerceIn(1, 30)

        connectButton.isEnabled = false
        statusText.text = "وضعیت: در حال اتصال..."
        worker.execute {
            try {
                val ssh = OltSshClient(host, sshPort, user, pass)
                ssh.connect()
                client = ssh
                connected = true
                main.post {
                    connectButton.isEnabled = true
                    connectButton.text = "قطع اتصال"
                    connectButton.setBackground(round(Color.rgb(190, 65, 65), 14))
                    statusText.text = "وضعیت: متصل به $host"
                }
                pollTask = worker.scheduleAtFixedRate({
                    try {
                        val result = ssh.readMetrics(frame, slot, port, cpuSlot)
                        main.post { render(result) }
                    } catch (e: Exception) {
                        main.post { statusText.text = "خطای دریافت اطلاعات: " + (e.message ?: "ارتباط قطع شد") }
                    }
                }, 0, interval.toLong(), TimeUnit.SECONDS)
            } catch (e: Exception) {
                connected = false
                main.post {
                    connectButton.isEnabled = true
                    statusText.text = "اتصال ناموفق: " + (e.message ?: "خطای SSH")
                }
            }
        }
    }

    private fun stopMonitoring() {
        pollTask?.cancel(true)
        pollTask = null
        connected = false
        worker.execute {
            try { client?.close() } catch (_: Exception) {}
            client = null
        }
        connectButton.text = "اتصال به OLT و شروع پایش"
        connectButton.setBackground(round(blue, 14))
        statusText.text = "وضعیت: قطع"
    }

    private fun render(m: OltMetrics) {
        rxText.text = (m.rxKbps?.fmt() ?: "—") + " Kbit/s"
        txText.text = (m.txKbps?.fmt() ?: "—") + " Kbit/s"
        rxPpsText.text = (m.rxPps?.fmt0() ?: "—") + " pps"
        txPpsText.text = (m.txPps?.fmt0() ?: "—") + " pps"
        cpuText.text = m.cpu?.let { "$it%" } ?: "—"
        memText.text = m.memory?.let { "$it%" } ?: "—"
        tempText.text = m.temperature?.let { "$it °C" } ?: "—"
        fanText.text = m.fan ?: "نامشخص"
        uplink8Text.text = m.uplink8 ?: "نامشخص"
        uplink9Text.text = m.uplink9 ?: "نامشخص"
        chart.addSample(m.rxKbps ?: 0.0, m.txKbps ?: 0.0)
        statusText.text = "وضعیت: متصل · آخرین بروزرسانی " + java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())
    }

    private fun sectionTitle(text: String) = label(text, 16, ink, true).apply {
        setPadding(dp(2), dp(18), dp(2), dp(8))
    }

    private fun card(color: Int) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(15), dp(16), dp(15))
        background = round(color, 18)
        elevation = dp(2).toFloat()
        layoutDirection = View.LAYOUT_DIRECTION_RTL
    }

    private fun row(parent: LinearLayout) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        layoutDirection = View.LAYOUT_DIRECTION_RTL
        parent.addView(this, matchWrap())
    }

    private fun field(parent: LinearLayout, title: String, hint: String, numeric: Boolean = false, password: Boolean = false): EditText {
        val holder = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        holder.addView(label(title, 11, muted))
        val edit = EditText(this).apply {
            textSize = 14f
            setSingleLine(true)
            setTextColor(ink)
            setHintTextColor(Color.rgb(160, 174, 187))
            this.hint = hint
            setPadding(dp(10), 0, dp(10), 0)
            background = round(Color.rgb(246, 249, 252), 10)
            inputType = when {
                password -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                numeric -> InputType.TYPE_CLASS_NUMBER
                else -> InputType.TYPE_CLASS_TEXT
            }
            layoutDirection = View.LAYOUT_DIRECTION_LTR
            textDirection = View.TEXT_DIRECTION_LTR
        }
        holder.addView(edit, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(48)).apply {
            topMargin = dp(4); bottomMargin = dp(9)
        })
        val params = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply {
            if (parent.orientation == LinearLayout.HORIZONTAL) marginStart = dp(6)
        }
        parent.addView(holder, if (parent.orientation == LinearLayout.HORIZONTAL) params else matchWrap())
        return edit
    }

    private fun metric(parent: LinearLayout, title: String, value: String, accent: Int): TextView {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(10), dp(10), dp(10), dp(10))
            background = round(Color.rgb(246, 249, 252), 12)
        }
        box.addView(label(title, 11, muted))
        val valueView = label(value, 17, accent, true)
        box.addView(valueView)
        parent.addView(box, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply {
            marginStart = dp(5); marginEnd = dp(5); topMargin = dp(5)
        })
        return valueView
    }

    private fun label(text: String, size: Int, color: Int, bold: Boolean = false) = TextView(this).apply {
        this.text = text
        textSize = size.toFloat()
        setTextColor(color)
        if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
        gravity = Gravity.START
        layoutDirection = View.LAYOUT_DIRECTION_RTL
        setPadding(0, dp(2), 0, dp(2))
    }

    private fun round(color: Int, radius: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
    }

    private fun matchWrap(height: Int = LinearLayout.LayoutParams.WRAP_CONTENT) =
        LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, height).apply { bottomMargin = dp(8) }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onDestroy() {
        stopMonitoring()
        worker.shutdownNow()
        super.onDestroy()
    }
}

private data class OltMetrics(
    val rxKbps: Double? = null,
    val txKbps: Double? = null,
    val rxPps: Double? = null,
    val txPps: Double? = null,
    val cpu: Int? = null,
    val memory: Int? = null,
    val temperature: Int? = null,
    val fan: String? = null,
    val uplink8: String? = null,
    val uplink9: String? = null
)

private class OltSshClient(
    private val host: String,
    private val port: Int,
    private val username: String,
    private val password: String
) {
    private var session: Session? = null
    private var channel: ChannelShell? = null
    private var input: InputStream? = null
    private var output: OutputStream? = null

    @Synchronized
    fun connect() {
        val s = JSch().getSession(username, host, port)
        s.setPassword(password)
        // Internal-network prototype; host-key pinning is required before production use.
        s.setConfig("StrictHostKeyChecking", "no")
        s.setServerAliveInterval(15000)
        s.connect(12000)
        val ch = s.openChannel("shell") as ChannelShell
        ch.setPtyType("vt100")
        ch.connect(8000)
        session = s
        channel = ch
        input = ch.inputStream
        output = ch.outputStream
        Thread.sleep(500)
        drain()
    }

    @Synchronized
    fun readMetrics(frame: Int, slot: Int, portNumber: Int, cpuSlot: String): OltMetrics {
        check(session?.isConnected == true && channel?.isConnected == true) { "SSH session is not connected" }
        execute("config")
        execute("interface giu $frame/$slot")
        val traffic = execute("display port traffic $portNumber")
        execute("quit")
        val cpuOut = execute("display resource occupancy cpu")
        val memOut = execute("display resource occupancy mem")
        val tempOut = execute("display temperature $cpuSlot")
        val emuOut = execute("display emu 0")
        val boardOut8 = execute("display board $frame/8")
        val boardOut9 = execute("display board $frame/9")

        return OltMetrics(
            rxKbps = number(traffic, "received traffic of this port\\(kbits/s\\)"),
            txKbps = number(traffic, "transmitted traffic of this port\\(kbits/s\\)"),
            rxPps = number(traffic, "received traffic of this port\\(packets/s\\)"),
            txPps = number(traffic, "transmitted traffic of this port\\(packets/s\\)"),
            cpu = percent(cpuOut),
            memory = percent(memOut),
            temperature = Regex("temperature of the board:\\s*(\\d+)C", RegexOption.IGNORE_CASE)
                .find(tempOut)?.groupValues?.get(1)?.toIntOrNull(),
            fan = Regex("FAN\\s+(normal|abnormal|failure|fault)", RegexOption.IGNORE_CASE)
                .find(emuOut)?.groupValues?.get(1)?.lowercase(),
            uplink8 = linkSummary(boardOut8),
            uplink9 = linkSummary(boardOut9)
        )
    }

    private fun linkSummary(text: String): String? {
        val matches = Regex("(?m)^\\s*(\\d+)\\s+GE\\s+\\S+\\s+\\d+\\s+\\S+\\s+\\S+\\s+\\S+\\s+\\S+\\s+\\S+\\s+(online|offline)", RegexOption.IGNORE_CASE)
            .findAll(text)
            .map { "GE" + it.groupValues[1] + " " + it.groupValues[2] }
            .toList()
        return matches.takeIf { it.isNotEmpty() }?.joinToString(" · ")
    }
    private fun number(text: String, labelPattern: String): Double? {
        val regex = Regex("$labelPattern\\s*=\\s*([0-9]+(?:\\.[0-9]+)?)", RegexOption.IGNORE_CASE)
        return regex.find(text)?.groupValues?.get(1)?.toDoubleOrNull()
    }

    private fun percent(text: String): Int? =
        Regex("(?:occupancy|usage rate)[^\\r\\n]*?(\\d+)\\s*%", RegexOption.IGNORE_CASE)
            .find(text)?.groupValues?.get(1)?.toIntOrNull()

    private fun execute(command: String): String {
        val out = output ?: error("SSH output stream unavailable")
        out.write((command + "\n").toByteArray(Charsets.UTF_8))
        out.flush()
        return readUntilQuiet()
    }

    private fun readUntilQuiet(): String {
        val stream = input ?: error("SSH input stream unavailable")
        val result = StringBuilder()
        var lastByteAt = System.currentTimeMillis()
        val started = lastByteAt
        val buffer = ByteArray(4096)
        while (System.currentTimeMillis() - started < 7000) {
            while (stream.available() > 0) {
                val n = stream.read(buffer, 0, minOf(buffer.size, stream.available()))
                if (n > 0) {
                    result.append(String(buffer, 0, n, Charsets.UTF_8))
                    lastByteAt = System.currentTimeMillis()
                }
            }
            if (result.isNotEmpty() && System.currentTimeMillis() - lastByteAt > 550) break
            Thread.sleep(60)
        }
        return result.toString()
    }

    private fun drain() {
        val stream = input ?: return
        val buffer = ByteArray(2048)
        while (stream.available() > 0) stream.read(buffer, 0, minOf(buffer.size, stream.available()))
    }

    @Synchronized
    fun close() {
        try { channel?.disconnect() } catch (_: Exception) {}
        try { session?.disconnect() } catch (_: Exception) {}
        channel = null
        session = null
        input = null
        output = null
    }
}

private class TrafficChartView(context: android.content.Context) : View(context) {
    private val rx = ArrayDeque<Float>()
    private val tx = ArrayDeque<Float>()
    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(228, 236, 243); strokeWidth = 1.5f }
    private val rxPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(30, 190, 200); strokeWidth = 4f
        style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND
    }
    private val txPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(26, 113, 196); strokeWidth = 4f
        style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(111, 130, 149); textSize = 26f }

    fun addSample(rxValue: Double, txValue: Double) {
        rx.addLast(rxValue.toFloat())
        tx.addLast(txValue.toFloat())
        while (rx.size > 60) rx.removeFirst()
        while (tx.size > 60) tx.removeFirst()
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val left = 12f
        val right = width - 12f
        val top = 18f
        val bottom = height - 24f
        for (i in 0..3) {
            val y = top + (bottom - top) * i / 3f
            canvas.drawLine(left, y, right, y, gridPaint)
        }
        if (rx.size < 2) {
            canvas.drawText("Waiting for traffic data...", left + 8f, height / 2f, textPaint)
            return
        }
        val maxValue = max(1f, max(rx.maxOrNull() ?: 0f, tx.maxOrNull() ?: 0f) * 1.15f)
        drawLine(canvas, rx.toList(), maxValue, left, right, top, bottom, rxPaint)
        drawLine(canvas, tx.toList(), maxValue, left, right, top, bottom, txPaint)
    }

    private fun drawLine(
        canvas: Canvas, values: List<Float>, maxValue: Float,
        left: Float, right: Float, top: Float, bottom: Float, paint: Paint
    ) {
        if (values.size < 2) return
        val path = Path()
        values.forEachIndexed { i, v ->
            val x = left + (right - left) * i / (values.size - 1).toFloat()
            val y = bottom - (v / maxValue) * (bottom - top)
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        canvas.drawPath(path, paint)
    }
}

private fun Double.fmt(): String = String.format(java.util.Locale.US, "%,.1f", this)
private fun Double.fmt0(): String = String.format(java.util.Locale.US, "%,.0f", this)
