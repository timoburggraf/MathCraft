"""Synthetic authorization and replay checks; no live data, devices or paid models."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import sys
import secrets
import tempfile
import unittest
import shutil
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tutor"))
import server
import eltern
import lehrer
import speicher
from security import COOKIE


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mathcraft-security-test-")
        self.addCleanup(self.tmp.cleanup)
        self.now = 2000000000
        self.password = secrets.token_urlsafe(24)  # pro Lauf neu, nie ein fester Wert
        self.app = server.build_app({"TESTING": True, "MC_STATE_HOME": self.tmp.name,
                     "MATHCRAFT_PARENT_PASSWORD": self.password,
                     "MATHCRAFT_SESSION_KEY": "synthetic-session-signing-key-only-tests",
                     "MATHCRAFT_DEVICE_KEY": "synthetic-device-root-key-only-tests",
                     "MC_TEST_CLOCK": lambda: self.now})
        self.client = self.app.test_client()
        self.access = self.app.extensions["mathcraft_security"]
        self.dev = "1234567890abcdef"
        self.base = "https://localhost"

    def get(self, path, **kwargs):
        return self.client.get(path, base_url=self.base, **kwargs)

    def post(self, path, **kwargs):
        return self.client.post(path, base_url=self.base, **kwargs)

    def login(self):
        form = self.get("/login")
        token = re.search(r'name="csrf" value="([^"]+)"', form.text).group(1)
        return self.post("/login", data={"csrf": token, "password": self.password},
                         headers={"Origin": self.base})

    def csrf(self):
        with self.access.connect() as db:
            return db.execute("SELECT csrf FROM sessions ORDER BY expires DESC LIMIT 1").fetchone()[0]

    def pair(self, paid=False):
        code = self.access.pair_code(self.dev, paid)
        result = self.post("/pair", json={"dev": self.dev, "code": code}, headers={"Origin": "https://localhost"})
        self.assertEqual(result.status_code, 200)
        return result.json["key"]

    def signed(self, key, path, payload, nonce="a"*32, stamp=None, dev=None):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        stamp = str(self.now if stamp is None else stamp)
        canonical = "\n".join(("POST", path, stamp, nonce, hashlib.sha256(raw).hexdigest()))
        signature = hmac.new(key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {"X-MC-Device": dev or self.dev, "X-MC-Time": stamp,
                   "X-MC-Nonce": nonce, "X-MC-Signature": signature, "Content-Type": "application/json"}
        return raw, headers

    def test_provider_exception_content_is_not_sent_to_device(self):
        import erklaerer
        from types import SimpleNamespace
        def fail(**kwargs):
            raise RuntimeError("synthetic-sensitive-provider-detail-for-test")
        client = SimpleNamespace(messages=SimpleNamespace(stream=fail))
        with patch("erklaerer.aufgabe", return_value=({"skill": "synthetic", "stage": 1}, {"type": "zahl", "q": "fixture"})):
            result = list(erklaerer.erklaere_stream("synthetic-unit", 0, client=client, ohne_cache=True))
        self.assertEqual(result, [("weg", "Aufruf gescheitert: RuntimeError")])

    def test_anonymous_parent_and_paid_routes_fail_closed(self):
        for path in ["/eltern", "/zaehlstand"]:
            self.assertEqual(self.get(path).status_code, 401)
        for path in ["/tutor", "/tutor-jetzt", "/wunsch", "/geraet", "/sync", "/erklaer"]:
            self.assertEqual(self.post(path, json={}).status_code, 401)

    def test_all_private_http_including_login_refused(self):
        for path in ["/eltern", "/login", "/sync", "/pair"]:
            self.assertEqual(self.client.get(path, base_url="http://localhost").status_code, 426)
        self.assertEqual(self.client.get("/health", base_url="http://localhost").status_code, 200)

    def test_login_secure_cookie_legitimate_view_and_logout(self):
        result = self.login()
        self.assertEqual(result.status_code, 303)
        cookie = result.headers["Set-Cookie"]
        for flag in ["Secure", "HttpOnly", "SameSite=Strict", "Path=/"]:
            self.assertIn(flag, cookie)
        with patch.object(eltern, "seite", return_value='<html><form method="post" action="/geraet"></form></html>'):
            page = self.get("/eltern")
        self.assertEqual(page.status_code, 200)
        self.assertIn('name="csrf"', page.text)
        self.assertIn("/device/pair-code", page.text)
        self.assertEqual(self.post("/logout", data={"csrf": self.csrf()}).status_code, 303)
        self.assertEqual(self.get("/eltern").status_code, 401)

    def test_parent_post_requires_one_time_csrf_and_same_origin(self):
        self.login(); token = self.csrf()
        self.assertEqual(self.post("/geraet", data={"dev": self.dev, "art": "aus"}).status_code, 403)
        self.assertEqual(self.post("/geraet", data={"dev": self.dev, "art": "aus", "csrf": token},
                                   headers={"Origin": "https://attacker.invalid"}).status_code, 403)
        with patch.object(speicher, "ignoriert_setzen") as changed:
            result = self.post("/geraet", data={"dev": self.dev, "art": "aus", "csrf": token})
            self.assertEqual(result.status_code, 303); changed.assert_called_once()
            self.assertEqual(self.post("/geraet", data={"dev": self.dev, "art": "aus", "csrf": token}).status_code, 403)

    def test_login_form_replay_and_login_csrf_refused(self):
        form = self.get("/login"); token = re.search(r'name="csrf" value="([^"]+)"', form.text).group(1)
        self.assertEqual(self.post("/login", data={"csrf": token, "password": self.password},
                                   headers={"Origin": "https://attacker.invalid"}).status_code, 403)
        self.assertEqual(self.post("/login", data={"csrf": token, "password": self.password}).status_code, 303)
        self.assertEqual(self.post("/login", data={"csrf": token, "password": self.password}).status_code, 403)

    def test_wrong_password_and_guessing_limit(self):
        for index in range(6):
            form = self.get("/login"); token = re.search(r'name="csrf" value="([^"]+)"', form.text).group(1)
            result = self.post("/login", data={"csrf": token, "password": "wrong-synthetic"})
            self.assertEqual(result.status_code, 401 if index < 5 else 429)

    def test_pair_code_one_use_expiration_and_device_binding(self):
        code = self.access.pair_code(self.dev)
        self.assertEqual(self.post("/pair", json={"dev": "abcdef0123456789", "code": code}).status_code, 401)
        self.assertEqual(self.post("/pair", json={"dev": self.dev, "code": code}).status_code, 200)
        self.assertEqual(self.post("/pair", json={"dev": self.dev, "code": code}).status_code, 401)
        code = self.access.pair_code(self.dev); self.now += 301
        self.assertEqual(self.post("/pair", json={"dev": self.dev, "code": code}).status_code, 401)

    def test_signed_sync_own_device_only_and_no_paid_generation(self):
        key = self.pair()
        raw, headers = self.signed(key, "/sync", {"dev": self.dev, "ev": []})
        with patch.object(speicher, "schreibe", return_value=(0, 0)), patch.object(speicher, "wuensche_lesen", return_value=[]), patch.object(lehrer, "lies_plan", return_value=None), \
             patch.object(lehrer, "vielleicht_nachdenken") as paid:
            self.assertEqual(self.post("/sync", data=raw, headers=headers).status_code, 200)
            paid.assert_not_called()
        raw, headers = self.signed(key, "/sync", {"dev": "abcdef0123456789", "ev": []}, nonce="b"*32)
        with patch.object(speicher, "schreibe") as changed:
            self.assertEqual(self.post("/sync", data=raw, headers=headers).status_code, 403);changed.assert_not_called()

    def test_signature_body_path_and_timestamp_binding(self):
        key = self.pair();raw, headers = self.signed(key, "/sync", {"dev": self.dev, "ev": []})
        self.assertEqual(self.post("/sync", data=raw+b" ", headers=headers).status_code, 401)
        self.assertEqual(self.post("/erklaer", data=raw, headers=headers).status_code, 401)
        raw, headers = self.signed(key, "/sync", {}, stamp=self.now-301)
        self.assertEqual(self.post("/sync", data=raw, headers=headers).status_code, 401)

    def test_device_replay_rejected_across_new_app_instance(self):
        key=self.pair();raw,headers=self.signed(key,"/sync",{"dev":"abcdef0123456789","ev":[]})
        self.assertEqual(self.post("/sync",data=raw,headers=headers).status_code,403)
        self.assertEqual(self.post("/sync",data=raw,headers=headers).status_code,409)
        other=server.build_app(dict(self.app.config));client=other.test_client()
        self.assertEqual(client.post("/sync",data=raw,headers=headers,base_url=self.base).status_code,409)

    def test_revocation_immediate_and_paid_permission_separate(self):
        key=self.pair();raw,headers=self.signed(key,"/erklaer",{"u":"synthetic-unit","i":0})
        with patch("erklaerer.erklaere_stream") as paid:
            self.assertEqual(self.post("/erklaer",data=raw,headers=headers).status_code,403);paid.assert_not_called()
        self.login();self.assertEqual(self.post("/device/revoke",data={"csrf":self.csrf(),"dev":self.dev}).status_code,303)
        raw,headers=self.signed(key,"/sync",{"dev":self.dev,"ev":[]},nonce="b"*32)
        self.assertEqual(self.post("/sync",data=raw,headers=headers).status_code,401)

    def test_paid_explanation_daily_limit_with_fake_model(self):
        key=self.pair(paid=True)
        for index in range(11):
            self.now += 61
            raw,headers=self.signed(key,"/erklaer",{"u":"synthetic-unit","i":0},nonce=f"{index:032x}")
            with patch("erklaerer.erklaere_stream",return_value=iter([("txt","synthetic explanation")])):
                result=self.post("/erklaer",data=raw,headers=headers,buffered=True)
                self.assertEqual(result.status_code,200 if index<10 else 429)

    def test_cors_restricted_and_parent_response_never_shared(self):
        self.assertNotIn("Access-Control-Allow-Origin",self.get("/eltern",headers={"Origin":"https://attacker.invalid"}).headers)
        self.assertEqual(self.post("/pair",json={},headers={"Origin":"https://attacker.invalid"}).status_code,403)
        result=self.client.options("/sync",base_url=self.base,headers={"Origin":"https://localhost"})
        self.assertEqual(result.status_code,204)
        self.assertEqual(result.headers["Access-Control-Allow-Origin"],"https://localhost")
        self.assertNotIn("Access-Control-Allow-Credentials",result.headers)

    def test_host_rebinding_payload_size_and_session_expiry(self):
        self.assertEqual(self.get("/health",headers={"Host":"attacker.invalid"}).status_code,400)
        self.assertEqual(self.post("/pair",data=b"x"*(server.MAX_BODY+1),content_type="application/json").status_code,413)
        self.login();self.now+=8*3600+1;self.assertEqual(self.get("/eltern").status_code,401)

    @unittest.skipUnless(shutil.which("node"), "Node required for actual frontend/server protocol compatibility")
    def test_actual_frontend_signature_matches_server_and_never_follows_new_host(self):
        key = self.pair()
        source = (ROOT / "src/app.html").read_text()
        block = source[source.index("const serverUrl ="):source.index("/* ===== End secure device connection.")]
        bootstrap = """const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const crypto=require('node:crypto').webcrypto;
const S={dev:input.dev,server:'https://localhost'}; const NATIVE=false, CAP={};
const localStorage={getItem:()=>JSON.stringify({...input,server:'https://localhost',expires:input.now+3600})};
const now=input.now; const RealDate=Date; global.Date=class extends RealDate{static now(){return now*1000;}};
let captured; const fetch=async(url,options)=>{captured={url,...options};return {ok:true};};
"""
        tail = """(async()=>{await privateRequest('/sync',{dev:S.dev,ev:[]});const first=captured;
S.server='https://attacker.invalid';let refused=false;try{await privateRequest('/sync',{});}catch(e){refused=true;}
process.stdout.write(JSON.stringify({first,refused}));})().catch(()=>process.exit(1));"""
        process = subprocess.run(["node", "-e", bootstrap + block + tail],
                                 input=json.dumps({"dev":self.dev,"key":key,"now":self.now}),
                                 capture_output=True,text=True,check=True)
        result=json.loads(process.stdout)
        self.assertTrue(result["refused"])
        self.assertEqual(result["first"]["credentials"],"omit")
        with patch.object(speicher,"schreibe",return_value=(0,0)),patch.object(speicher,"wuensche_lesen",return_value=[]), \
             patch.object(lehrer,"lies_plan",return_value=None):
            response=self.post("/sync",data=result["first"]["body"],headers=result["first"]["headers"])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")


if __name__ == "__main__":
    unittest.main()
