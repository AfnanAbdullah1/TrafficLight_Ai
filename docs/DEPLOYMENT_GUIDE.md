# 🚦 Remote Deployment Guide (Lab-to-Home Remote Access)

Yeh guide aapko step-by-step batati hai ke aap apne Lab mein chalne wale AI Traffic Light System ko **dunya mein kahin se bhi (ghar baithe ya mobile data se)** kaise control aur monitor kar sakte hain.

---

## 🛠️ Step 1: Pre-Deployment Checklist (Lab Setup)

Sabse pehle check karein ke Lab mein saara hardware local level par sahi chal raha hai:
1. Laptop aur saare boards (ESP32 WROOM + 3× ESP32-CAMs) **ek hi WiFi network** (hotspot) se connected hone chahiye.
2. Windows laptop par mDNS resolve hona chahiye. Agar windows `.local` addresses resolve nahi kar raha to:
   * Laptop par [Apple Bonjour Service](https://support.apple.com/kb/DL999) install kar lein.
3. Locally test karein: Python server start karein aur browser mein `http://localhost:5000` open kar ke check karein ke **"Connect All"** button click karne par camera feeds chal rahi hain aur signals control ho rahe hain.

---

## 🏆 Step 2: Option A - Ngrok Tunneling Setup (Recommended & Easiest)

Ngrok aapke local port `5000` ko internet par expose kar ke ek secure `https://...` link bana deta hai jise aap kahin se bhi access kar sakte hain.

### 1. Download & Auth (Sirf ek baar karna hai):
1. [Ngrok Sign Up](https://dashboard.ngrok.com/signup) par jaa kar free account banayein.
2. Windows ke liye Ngrok Agent download karein.
3. Windows terminal (CMD/PowerShell) open kar ke, jahan ngrok save kiya hai wahan jayein aur apna Authtoken add karein (token aapke ngrok dashboard par hoga):
   ```powershell
   ngrok config add-authtoken YOUR_PERSONAL_AUTH_TOKEN
   ```
4. *Optional (Highly Recommended):* Ngrok dashboard par **Domains** section mein jaa kar ek **Free Static Domain** claim kar lein (jaise `custom-traffic.ngrok-free.app`). Is se link har baar restart hone par change nahi hoga.

### 2. Run the System:
1. Humne aapke liye ek automated tool [start_system.bat](../scripts/start_system.bat) banaya hai.
2. Is file par double-click karein:
   * Yeh background mein auto-detect karega aur aapki Flask app + Ngrok tunnel dono alag console windows mein launch kar dega.
3. Agar Ngrok manually run karna ho, to run karein:
   ```powershell
   ngrok http 5000
   ```
   *(Or if you registered a free domain):*
   ```powershell
   ngrok http --url=YOUR-STATIC-DOMAIN.ngrok-free.app 5000
   ```
4. Terminal par jo **Forwarding URL** (`https://xxxx.ngrok-free.app`) show ho raha hai, usko copy kar lein.

---

## ☁️ Step 3: Option B - Cloudflare Tunnels (100% Free & Persistent Subdomain)

Agar aap chahte hain ke links kabhi expire na hon aur custom domains (jaise `traffic.myproject.com`) ke sath permanently remote control chalta rahe:

1. [Cloudflare](https://www.cloudflare.com/) par free account banayein aur apna custom domain add karein.
2. Cloudflare Zero Trust Dashboard par jaa kar **Networks** -> **Tunnels** par click karein.
3. **Create a Tunnel** par click karein aur `cloudflared` select karein.
4. Dashboard par di gayi command se `cloudflared` agent apne Windows laptop par download aur install karein (it runs as a background service).
5. Tunnel settings mein **Public Hostname** add karein:
   * **Subdomain:** `traffic`
   * **Domain:** `yourdomain.com`
   * **Service Type:** `HTTP`
   * **URL:** `localhost:5000`
6. Ab aapka server permanently `https://traffic.yourdomain.com` par dunya bhar se accessible rahega jab tak laptop aur boards Lab mein connect hain.

---

## 📱 Step 4: How to Access and Control from Home (Ghar Baithe Control Kaise Karein)

1. Lab mein laptop ko active rakhain aur check karein ke laptop screen off (Sleep mode) na ho.
2. Ghar baithe apne mobile ya personal laptop par home WiFi ya Mobile Data (4G/5G) turn on karein.
3. Browser mein apna public Ngrok ya Cloudflare link (`https://xxxx.ngrok-free.app`) open karein.
4. Aapka remote dashboard load ho jayega!
5. **Testing remote functionality:**
   * AI camera stream frames direct dashboard par show honge.
   * Emergency alerts ya Manual signal changing buttons press karein. Lab mein physical LEDs foran switch hongi.
   * Keyboard shortcuts (keys `1`, `2`, `3`, `A`, `M`, `Esc`) remote browser se bhi command send karein gi.

---

## 🔍 Troubleshooting (Common Problems & Fixes)

### 1. Dashboard opens, but Camera Stream shows "No Stream" (Camera local network error)
* **Wajah:** Laptop local mDNS se camera IP resolve nahi kar paa raha.
* **Fix:** 
  1. Check karein ke ESP32-CAMs actual active hain (Serial monitor par local IP check karein).
  2. Laptop par Bonjour install karein ya raw IP direct dashboard par type kar ke `Set` karein.
  3. Lab network par check karein ke client-to-client traffic block to nahi (kuch routers devices ko aapas mein ping nahi karne dete).

### 2. "Cannot reach server" error on remote device
* **Wajah:** Ngrok server ya Flask app crash ho gayi hai ya laptop sleep mode mein chala gaya hai.
* **Fix:**
  1. Lab laptop par power settings mein "Put the computer to sleep" ko **Never** par set karein.
  2. Dono console windows (Python aur Ngrok) ko check karein ke wo open hain ya nahi.

### 3. ESP32 Disconnected (Red badge on dashboard)
* **Wajah:** ESP32 controller offline chala gaya hai ya connection break ho gaya hai.
* **Fix:** ESP32 board ko power reset (restart) karein taake woh dobara WiFi hotspot se connect ho sake, aur dashboard par **Connect** button press karein.
