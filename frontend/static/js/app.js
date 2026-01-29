// =====================================================
// Women Safety Web - Frontend Controller (FINAL)
// OTP + Setup + Dashboard + WhatsApp Emergency Mode
// =====================================================

// 🔴 CHANGE THIS TO YOUR RENDER BACKEND URL
const API_BASE = "https://womens-saftey-web.onrender.com";

// ----------------------
// Helpers
// ----------------------
function qs(id) {
  return document.getElementById(id);
}

function isValidPhone(phone) {
  return /^[0-9]{10}$/.test(phone);
}

function nowTime() {
  return new Date().toLocaleString();
}

function getToken() {
  return localStorage.getItem("auth_token") || "";
}

function setToken(token) {
  localStorage.setItem("auth_token", token);
}

function clearAuth() {
  localStorage.removeItem("auth_token");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ----------------------
// API Fetch Wrapper
// ----------------------
async function apiFetch(path, method = "GET", body = null, auth = false) {
  const headers = { "Content-Type": "application/json" };

  if (auth) {
    const token = getToken();
    if (!token) throw new Error("Session expired. Login again.");
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let data = {};

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = {};
  }

  if (!res.ok) {
    throw new Error(data.detail || "API request failed");
  }

  return data;
}

// =====================================================
// LOGIN PAGE – OTP (DEMO OTP VISIBLE)
// =====================================================
if (qs("sendOtpBtn")) {
  const mobileInput = qs("mobile");
  const sendOtpBtn = qs("sendOtpBtn");
  const otpSection = qs("otpSection");
  const verifyOtpBtn = qs("verifyOtpBtn");
  const statusText = qs("statusText");

  let otpSentFor = null;

  sendOtpBtn.onclick = async () => {
    const mobile = mobileInput.value.trim();

    if (!isValidPhone(mobile)) {
      statusText.textContent = "Enter a valid 10-digit mobile number.";
      return;
    }

    try {
      sendOtpBtn.disabled = true;
      statusText.textContent = "Sending OTP...";

      const data = await apiFetch("/auth/send-otp", "POST", { phone: mobile });

      // 🔥 DEMO OTP SHOWN HERE
      statusText.textContent = `OTP (Demo): ${data.otp}`;

      otpSentFor = mobile;
      localStorage.setItem("user_mobile", mobile);

      otpSection.classList.remove("hidden");
      verifyOtpBtn.classList.remove("hidden");

    } catch (err) {
      statusText.textContent = err.message;
    } finally {
      sendOtpBtn.disabled = false;
    }
  };

  verifyOtpBtn.onclick = async () => {
    const otp = qs("otp").value.trim();
    const mobile = mobileInput.value.trim();

    if (!otpSentFor || mobile !== otpSentFor) {
      statusText.textContent = "Re-send OTP for this number.";
      return;
    }

    try {
      verifyOtpBtn.disabled = true;
      statusText.textContent = "Verifying OTP...";

      const data = await apiFetch("/auth/verify-otp", "POST", {
        phone: mobile,
        otp: otp,
      });

      setToken(data.token);

      const existingProfile = localStorage.getItem("user_data");
      window.location.href = existingProfile ? "dashboard.html" : "setup.html";

    } catch (err) {
      statusText.textContent = err.message;
      verifyOtpBtn.disabled = false;
    }
  };
}

// =====================================================
// SETUP PAGE
// =====================================================
if (qs("saveContinueBtn")) {
  const setupStatus = qs("setupStatus");

  let locationEnabled = false;
  let cameraEnabled = false;
  let micEnabled = false;

  qs("locationBtn").onclick = () => {
    navigator.geolocation.getCurrentPosition(
      () => {
        locationEnabled = true;
        qs("locationBtn").textContent = "Enabled";
      },
      () => setupStatus.textContent = "Location permission denied."
    );
  };

  qs("cameraBtn").onclick = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true });
      s.getTracks().forEach(t => t.stop());
      cameraEnabled = true;
      qs("cameraBtn").textContent = "Enabled";
    } catch {
      setupStatus.textContent = "Camera permission denied.";
    }
  };

  qs("micBtn").onclick = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach(t => t.stop());
      micEnabled = true;
      qs("micBtn").textContent = "Enabled";
    } catch {
      setupStatus.textContent = "Microphone permission denied.";
    }
  };

  qs("saveContinueBtn").onclick = async () => {
    if (!locationEnabled || !cameraEnabled || !micEnabled) {
      setupStatus.textContent = "Enable all permissions.";
      return;
    }

    const userData = {
      name: qs("name").value.trim(),
      contacts: [
        { name: qs("c1_name").value.trim(), phone: qs("c1_phone").value.trim() },
        { name: qs("c2_name").value.trim(), phone: qs("c2_phone").value.trim() },
        { name: qs("c3_name").value.trim(), phone: qs("c3_phone").value.trim() },
        { name: qs("c4_name").value.trim(), phone: qs("c4_phone").value.trim() },
      ],
    };

    localStorage.setItem("user_data", JSON.stringify(userData));

    try {
      await apiFetch("/user/setup", "POST", userData, true);
      window.location.href = "dashboard.html";
    } catch (err) {
      setupStatus.textContent = err.message;
    }
  };
}

// =====================================================
// WHATSAPP EMERGENCY MODE
// =====================================================
async function triggerWhatsAppSOS(userData) {
  navigator.geolocation.getCurrentPosition(async pos => {
    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;

    try {
      await apiFetch("/user/location", "POST", { lat, lon }, true);
    } catch {}

    const msg = `
🚨 WOMEN SAFETY EMERGENCY 🚨

Name: ${userData.name}
📍 Location:
https://maps.google.com/?q=${lat},${lon}

⏰ Time: ${nowTime()}
`;

    const encoded = encodeURIComponent(msg);

    for (let c of userData.contacts) {
      window.open(`https://wa.me/91${c.phone}?text=${encoded}`, "_blank");
      await sleep(1200);
    }
  });
}

// =====================================================
// DASHBOARD
// =====================================================
if (qs("sosBtn")) {
  const dashStatus = qs("dashStatus");
  const dangerStatus = qs("dangerStatus");
  const scoreText = qs("scoreText");

  const userData = JSON.parse(localStorage.getItem("user_data"));
  let dangerScore = 0;

  function updateUI() {
    scoreText.textContent = `Score: ${dangerScore}`;

    if (dangerScore >= 70) {
      dangerStatus.textContent = "EMERGENCY";
      dangerStatus.className = "status-value emergency";
    } else if (dangerScore >= 40) {
      dangerStatus.textContent = "RISK";
      dangerStatus.className = "status-value risk";
    } else {
      dangerStatus.textContent = "SAFE";
      dangerStatus.className = "status-value safe";
    }
  }

  updateUI();

  qs("unsafeBtn").onclick = () => {
    dangerScore += 30;
    dashStatus.textContent = "Unsafe feeling reported.";
    updateUI();
  };

  qs("sosBtn").onclick = () => {
    dangerScore = 100;
    updateUI();
    triggerWhatsAppSOS(userData);
  };

  qs("sendAlertBtn").onclick = () => triggerWhatsAppSOS(userData);

  qs("photoBtn").onclick = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true });
      s.getTracks().forEach(t => t.stop());
      dashStatus.textContent = "Photo captured (demo).";
    } catch {
      dashStatus.textContent = "Camera permission denied.";
    }
  };

  qs("audioBtn").onclick = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach(t => t.stop());
      dashStatus.textContent = "Audio recorded (demo).";
    } catch {
      dashStatus.textContent = "Microphone permission denied.";
    }
  };

  qs("logoutBtn").onclick = () => {
    clearAuth();
    localStorage.clear();
    window.location.href = "login.html";
  };
}
