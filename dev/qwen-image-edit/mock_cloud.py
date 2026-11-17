"""Mock Comfy Cloud for qwen_image_edit. Usage: mock_cloud.py API_PORT STORE_PORT MODE

MODE: ok | fail | slow | badnode | badupload
Prints `LEAK!` to stderr if the API key is ever sent to the storage host, and
`BADGRAPH:` if a submitted graph does not wire up the way the harness promises.
"""
import hashlib, json, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

API_PORT, STORE_PORT = int(sys.argv[1]), int(sys.argv[2])
MODE = sys.argv[3]
JOBS, UPLOADS = {}, {}
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 4096
IMAGE_KEYS = ("image1", "image2", "image3")
ASPECTS = ("1:1 (Square)", "2:3 (Portrait Photo)", "3:2 (Photo)", "3:4 (Portrait Standard)",
           "4:3 (Standard)", "9:16 (Portrait Widescreen)", "16:9 (Widescreen)",
           "21:9 (Ultrawide)")


def link(g, nid, slot):
    """(node, output) of nid's input slot, or None when it is not a link."""
    v = g.get(nid, {}).get("inputs", {}).get(slot)
    return tuple(v) if isinstance(v, list) and len(v) == 2 else None


def uploaded(g, lid):
    """The cloud name behind a LoadImage node id, or None when it is not one."""
    node = g.get(lid, {})
    if node.get("class_type") != "LoadImage":
        return None
    return node.get("inputs", {}).get("image")


def check_graph(g):
    """Return a list of problems; empty means the graph looks right."""
    bad = []
    ks = [nid for nid, n in g.items() if n["class_type"] == "KSampler"]
    if len(ks) != 1:
        return [f"expected exactly one KSampler, found {len(ks)}"]
    ks = ks[0]
    inp = g[ks]["inputs"]

    # --- exactly two Qwen edit encoders, wired to positive and negative
    enc = {}
    for slot in ("positive", "negative"):
        src = inp.get(slot)
        node = g.get(src[0], {}) if isinstance(src, list) and len(src) == 2 else {}
        if node.get("class_type") != "TextEncodeQwenImageEditPlus":
            bad.append(f"KSampler {slot} is not a TextEncodeQwenImageEditPlus")
            continue
        enc[slot] = (src[0], node["inputs"])
    allq = [nid for nid, n in g.items() if n["class_type"] == "TextEncodeQwenImageEditPlus"]
    if len(allq) != 2:
        bad.append(f"expected exactly two TextEncodeQwenImageEditPlus, found {len(allq)}")
    if len(enc) == 2 and enc["positive"][0] == enc["negative"][0]:
        bad.append("KSampler positive and negative are the same encoder")

    # --- both encoders carry clip + vae and the same contiguous image1..3 links
    links = {}
    for slot, (nid, ein) in enc.items():
        if "clip" not in ein:
            bad.append(f"{nid} has no clip")
        if "vae" not in ein:
            bad.append(f"{nid} has no vae")
        keys = [k for k in IMAGE_KEYS if k in ein]
        if keys != list(IMAGE_KEYS[:len(keys)]):
            bad.append(f"{nid} image keys are not contiguous: {keys}")
        links[slot] = {k: tuple(ein[k]) for k in keys}
    if len(links) == 2 and links["positive"] != links["negative"]:
        bad.append("positive and negative have different image1..3 links")
    imgs = links.get("positive") or links.get("negative") or {}

    # --- image1 is scaled (the same node also feeds the VAEEncode); image2/3 straight
    scaled = None
    if "image1" in imgs:
        node = g.get(imgs["image1"][0], {})
        if node.get("class_type") != "FluxKontextImageScale":
            bad.append("image1 is not scaled with FluxKontextImageScale")
        else:
            scaled = imgs["image1"][0]
            src = link(g, scaled, "image")
            name = uploaded(g, src[0]) if src else None
            if name is None:
                bad.append("image1 scale does not come from a LoadImage")
            elif name not in UPLOADS.values():
                bad.append(f"image1 '{name}' was never uploaded")
    for key in ("image2", "image3"):
        if key not in imgs:
            continue
        name = uploaded(g, imgs[key][0])
        if name is None:
            bad.append(f"{key} does not come straight from a LoadImage")
        elif name not in UPLOADS.values():
            bad.append(f"{key} '{name}' was never uploaded")

    # --- latent: the reference encode, or an empty latent from the resolution selector
    lat = g.get(inp["latent_image"][0], {}) if isinstance(inp.get("latent_image"), list) \
        and len(inp["latent_image"]) == 2 else {}
    if lat.get("class_type") == "VAEEncode":
        if not scaled:
            bad.append("VAEEncode latent but image1 is not a FluxKontextImageScale")
        elif link(g, inp["latent_image"][0], "pixels") != (scaled, 0):
            bad.append("VAEEncode pixels is not the same FluxKontextImageScale as image1")
    elif lat.get("class_type") == "EmptyLatentImage":
        if inp.get("denoise", 1) < 1:
            bad.append("denoise < 1 with an EmptyLatentImage renders a flat field")
        w, h = link(g, inp["latent_image"][0], "width"), link(g, inp["latent_image"][0], "height")
        res = g.get(w[0], {}) if w else {}
        if res.get("class_type") != "ResolutionSelector":
            bad.append("EmptyLatentImage width is not from a ResolutionSelector")
        else:
            ri = res["inputs"]
            if ri.get("aspect_ratio") not in ASPECTS:
                bad.append(f"ResolutionSelector aspect '{ri.get('aspect_ratio')}' is not one of 8")
            if ri.get("multiple") != 32:
                bad.append("ResolutionSelector multiple is not 32")
            if not (h and h[0] == w[0] and h[1] == 1):
                bad.append("EmptyLatentImage height is not ResolutionSelector output 1")
    else:
        bad.append("KSampler latent is neither VAEEncode nor EmptyLatentImage")

    # --- model chain: KSampler <- CFGNorm <- ModelSamplingAuraFlow <- [LoRAs] <- loader
    norm = g.get(link(g, ks, "model")[0], {}) if link(g, ks, "model") else {}
    if norm.get("class_type") != "CFGNorm":
        bad.append("KSampler model does not end at CFGNorm")
        loader = None
    else:
        src = link(g, link(g, ks, "model")[0], "model")
        node = g.get(src[0], {}) if src else {}
        if node.get("class_type") != "ModelSamplingAuraFlow":
            bad.append("CFGNorm does not take ModelSamplingAuraFlow")
            loader = None
        else:
            loader, m = None, link(g, src[0], "model")
            while m:
                n = g.get(m[0], {})
                if n.get("class_type") == "LoraLoaderModelOnly":
                    m = link(g, m[0], "model")
                    continue
                if n.get("class_type") in ("CheckpointLoaderSimple", "UNETLoader"):
                    loader = m[0]
                break
            if loader is None:
                bad.append("model chain does not reach a CheckpointLoaderSimple or UNETLoader")
    loaders = [nid for nid, n in g.items()
               if n["class_type"] in ("CheckpointLoaderSimple", "UNETLoader")]
    if len(loaders) != 1:
        bad.append(f"expected exactly one model loader, found {len(loaders)}")
    elif loader and loaders[0] != loader:
        bad.append("the sampler's model chain does not use the graph's only loader")

    # --- save is a SaveImage on a VAEDecode, and clip/vae come from that loader
    dec_id, dec = None, {}
    save = g.get("save", {})
    if save.get("class_type") != "SaveImage":
        bad.append("no SaveImage node 'save'")
    else:
        d = link(g, "save", "images")
        if d and g.get(d[0], {}).get("class_type") == "VAEDecode":
            dec_id, dec = d[0], g[d[0]]
        else:
            bad.append("save does not take a VAEDecode")
    if loader:
        if g[loader]["class_type"] == "CheckpointLoaderSimple":
            for nid, ein in enc.values():
                if tuple(ein.get("clip") or ()) != (loader, 1):
                    bad.append(f"{nid} clip is not CheckpointLoaderSimple output 1")
                if tuple(ein.get("vae") or ()) != (loader, 2):
                    bad.append(f"{nid} vae is not CheckpointLoaderSimple output 2")
            if dec and link(g, dec_id, "vae") != (loader, 2):
                bad.append("VAEDecode vae is not CheckpointLoaderSimple output 2")
        else:
            enc_ids = [nid for nid, _ in enc.values()]
            clips = {link(g, nid, "clip") for nid in enc_ids}
            vaes = {link(g, nid, "vae") for nid in enc_ids}
            if dec:
                vaes.add(link(g, dec_id, "vae"))
            if None in clips or len(clips) != 1:
                bad.append("encoders do not share one CLIP source")
            else:
                cl = g.get(next(iter(clips))[0], {})
                if cl.get("class_type") != "CLIPLoader" or \
                        cl.get("inputs", {}).get("type") != "qwen_image":
                    bad.append("clip does not come from a CLIPLoader with type qwen_image")
            if None in vaes or len(vaes) != 1:
                bad.append("encoders and decoder do not share one VAE source")
            elif g.get(next(iter(vaes))[0], {}).get("class_type") != "VAELoader":
                bad.append("vae does not come from a VAELoader")

    for nid, n in g.items():  # every link must resolve
        for k, v in n["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in g:
                bad.append(f"{nid}.{k} links to missing node {v[0]}")
    return bad


def parse_multipart(ctype, raw):
    boundary = ctype.split("boundary=")[1].encode()
    fields, files = {}, {}
    for part in raw.split(b"--" + boundary):
        if b"\r\n\r\n" not in part:
            continue
        head, _, body = part.partition(b"\r\n\r\n")
        body = body[:-2] if body.endswith(b"\r\n") else body
        head = head.decode("utf-8", "replace")
        name = head.split('name="')[1].split('"')[0]
        if 'filename="' in head:
            files[name] = (head.split('filename="')[1].split('"')[0], body)
        else:
            fields[name] = body.decode()
    return fields, files


class Api(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, obj=None, headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items(): self.send_header(k, v)
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def auth(self):
        if self.headers.get("X-API-Key") != "sk-test-1234":
            self.send(401, {"code": "unauthorized", "message": "bad key"}); return False
        return True

    def do_POST(self):
        if not self.auth(): return
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/api/upload/image":
            if MODE == "badupload":
                return self.send(413, {"message": "file too large"})
            fields, files = parse_multipart(self.headers["Content-Type"], raw)
            if "image" not in files or fields.get("type") != "input":
                return self.send(400, {"message": "bad upload form"})
            fname, content = files["image"]
            name = hashlib.sha256(content).hexdigest() + "." + fname.rsplit(".", 1)[-1]
            UPLOADS[fname] = name
            return self.send(200, {"name": name, "subfolder": "", "type": "input"})
        body = json.loads(raw)
        if self.path == "/api/prompt":
            if MODE == "badnode":
                return self.send(400, {"error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation", "details": ""},
                    "node_errors": {"ckpt": {"errors": [{"type": "value_not_in_list", "message": "Value not in list", "details": "ckpt_name: 'nope.safetensors' not in [...]"}], "class_type": "CheckpointLoaderSimple"}}})
            problems = check_graph(body["prompt"])
            if problems:
                print("BADGRAPH:", "; ".join(problems), file=sys.stderr)
                return self.send(400, {"error": {"message": "mock: " + "; ".join(problems)}})
            pid = str(uuid.uuid4()); JOBS[pid] = {"t": time.time()}
            return self.send(200, {"prompt_id": pid, "number": 1, "node_errors": {}})
        if self.path == "/api/queue":
            return self.send(200, {})
        self.send(404, {"code": "nf", "message": "nf"})

    def do_GET(self):
        if not self.auth(): return
        u = urlsplit(self.path); q = parse_qs(u.query); parts = u.path.split("/")
        if u.path.startswith("/api/job/") and u.path.endswith("/status"):
            pid = parts[3]; j = JOBS.get(pid)
            if not j: return self.send(404, {"code": "nf", "message": "job not found"})
            age = time.time() - j["t"]
            st = "pending" if age < 1 else "in_progress" if (age < 4 or MODE == "slow") else ("error" if MODE == "fail" else "completed")
            return self.send(200, {"id": pid, "status": st, "created_at": "x", "updated_at": "x", "error_message": "CUDA OOM" if st == "error" else None})
        if u.path.startswith("/api/jobs/"):
            pid = parts[3]
            if MODE == "fail":
                return self.send(200, {"id": pid, "status": "failed", "create_time": 0, "update_time": 0,
                    "execution_error": {"node_id": "sampler", "node_type": "KSampler", "exception_type": "torch.OutOfMemoryError", "exception_message": "CUDA out of memory", "traceback": ["x"] * 50}})
            img = {"filename": "qwen_00001_.png", "subfolder": "", "type": "output"}
            return self.send(200, {"id": pid, "status": "completed", "create_time": 0, "update_time": 0, "workflow": {"big": "x" * 50000},
                "outputs": {"save": {"images": [img], "animated": [False]}}})
        if u.path == "/api/view":
            if not q.get("filename", [""])[0].endswith(".png"):
                return self.send(404, {"code": "nf", "message": "not a png"})
            return self.send(302, None, {"Location": f"http://127.0.0.1:{STORE_PORT}/bucket/{q['filename'][0]}?sig=abc"})
        if u.path == "/api/object_info" or u.path.startswith("/api/object_info/"):
            return self.send(200, {
                "UNETLoader": {"input": {"required": {"unet_name": ["COMBO", {"options":
                    ["qwen_image_edit_2509_fp8mixed.safetensors",
                     "qwen_image_edit_2511_fp8mixed.safetensors",
                     "qwen_image_edit_2511_bf16.safetensors",
                     "flux1-dev.safetensors"]}]}}},
                "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["COMBO", {"options":
                    ["Phr00t__Qwen-Image-Edit-Rapid-AIO__Qwen-Rapid-AIO-NSFW-v23.safetensors",
                     "sd_xl_base_1.0.safetensors"]}]}}},
                "LoraLoaderModelOnly": {"input": {"required": {"lora_name": ["COMBO", {"options":
                    ["Skin_Fix_rank64.safetensors",
                     "Qwen-Image-Edit-2509-Lightning-8steps-V1.0-bf16.safetensors",
                     "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-fp32.safetensors",
                     "example_style_a.safetensors"]}]}}},
                "CLIPLoader": {"input": {"required": {"clip_name": ["COMBO", {"options":
                    ["ethanfel__Qwen25-VL-7B-Huihui-Abliterated-ComfyUI-ConvRot-INT8__qwen_2.5_vl_7b_huihui_abliterated_int8_convrot.safetensors",
                     "qwen_2.5_vl_7b.safetensors"]}]}}},
                "KSampler": {"input": {"required": {
                    "sampler_name": ["COMBO", {"options": ["euler", "euler_ancestral", "dpmpp_2m"]}],
                    "scheduler": ["COMBO", {"options": ["simple", "beta", "normal"]}]}}},
            })
        self.send(404, {"code": "nf", "message": "nf"})


class Store(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.headers.get("X-API-Key") or self.headers.get("Authorization"):
            print("LEAK!", file=sys.stderr)
        self.send_response(200); self.send_header("Content-Length", str(len(PNG))); self.end_headers(); self.wfile.write(PNG)


threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STORE_PORT), Store).serve_forever, daemon=True).start()
ThreadingHTTPServer(("127.0.0.1", API_PORT), Api).serve_forever()
