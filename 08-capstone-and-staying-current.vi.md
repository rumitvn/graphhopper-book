# Chapter 08 — Capstone & Staying Current

> **Goal:** Tự đứng vững được trong codebase này. Sau chương này bạn sẽ đã ship ba capstone nhỏ (một custom
> profile, một isochrone, một truy vấn transit cho thành phố thật), đọc được một merged GraphHopper PR mà
> không cần ai dắt tay, và nắm đúng quy trình re-sync cuốn sách khi bạn re-pin sang một tag mới hơn. Pinned to
> **`11.0`** (`69e50f6`).

## 8.1 Vì sao quan trọng

Một cuốn sách mà bạn chỉ theo được khi có tác giả thuyết minh thì không phải là hiểu — đó là đi du lịch. Chương
này bỏ luôn người thuyết minh. Các capstone ép bạn *kết hợp* nhiều chương lại (một custom model từ Chương 4
định hình một algorithm từ Chương 3, phục vụ qua một endpoint từ Chương 7); đọc một PR ép bạn tự dò code từ
con số không; và re-pin dạy bạn rằng cuốn sách là một *phương pháp*, không phải một snapshot — số dòng có trôi
đi, nhưng tấm bản đồ bạn dựng về engine thì không.

## 8.2 Ba capstone

Làm theo thứ tự; mỗi cái tựa vào cái trước.

**Capstone 1 — một custom profile end to end (Chương 2–4, 7).** Thêm một profile mà một fleet thật sẽ cần:
một EV hoặc bus tránh một road class và tôn trọng một weight limit. Trong `config-example.yml` của bạn, thêm một
profile với `custom_model`, xoá `graph-cache/`, re-import, rồi query cả hai chiều:

```yaml
profiles:
  - name: bus
    custom_model:
      priority:
        - if: road_class == MOTORWAY
          multiply_by: 0.0        # buses off the motorway
        - if: max_weight < 7.5    # avoid bridges under 7.5t
          multiply_by: 0.0
      speed:
        - if: true
          limit_to: 60
```

Route cùng một A→B với `profile=car` và `profile=bus`; xác nhận hai path khác nhau và rằng phần khác biệt đó
khớp với luật của bạn. **Success:** bạn chỉ được ra đúng các encoded value `road_class`/`max_weight` (§4.6) mà
luật của bạn đọc, và giải thích được vì sao profile này không thể chạy CH (§3.5).

**Capstone 2 — dựng và render một isochrone (Chương 3, 7).** Gọi `/isochrone` cho 5, 10 và 15 phút từ một điểm;
chồng ba polygon lên bản đồ (web UI có sẵn ở `http://localhost:8989/` hoặc bất kỳ GeoJSON viewer nào).
**Success:** bạn giải thích được vì sao một isochrone là một *cây* shortest-path (`ShortestPathTree`, §7.5), chứ
không phải một tập các route độc lập, và vì sao polygon 15 phút bao trọn polygon 5 phút.

**Capstone 3 — transit của một thành phố thật (Chương 5).** Tải một GTFS feed thật (thành phố của chính bạn nếu
nó có công bố — một điểm nối tuyệt vời với BusMap/VinBus), import nó với một `pt` profile, rồi lên kế hoạch một
hành trình có transfer. **Success:** bạn đọc được các leg trả về, đếm được số transfer, và gọi tên được các tiêu
chí `Label` (§5.5) mà search đã đánh đổi để chọn ra itinerary đó.

## 8.3 Read a merged PR unaided

Chọn một GraphHopper PR mới merge gần đây có động tới routing, transit, hoặc map-matching (danh sách PR "Closed /
Merged" trên GitHub repo). Trước khi đọc phần mô tả, chỉ từ diff hãy trả lời:

1. Nó đổi **module** nào? (Ánh xạ về bảng module ở Chương 1.)
2. Đâu là **một `file:line` cốt lõi** nơi hành vi thực sự thay đổi — cái hunk chịu lực, không phải test hay
   changelog?
3. **Test** nào chứng minh hành vi mới, và input nào lẽ ra đã fail trước đó?

Rồi đọc phần mô tả và so lại. Nếu ba câu trả lời của bạn khớp với ý đồ tác giả, bạn đọc được codebase này. Nếu
không, cái *khoảng cách* đó chính là mục tiêu đọc kế tiếp — thường là một chương bạn mới lướt qua.

> 💡 Một PR đầu tiên tốt để luyện là bất kỳ cái nào động tới `CustomWeighting`, `MultiCriteriaLabelSetting`, hoặc
> một `EncodedValue` mới — cả ba đều là những chương bạn đã đọc, nên bạn đang kiểm tra mức thấu hiểu, chứ không
> học từ đầu.

## 8.4 Re-pinning: re-sync cuốn sách này sang một tag mới hơn

Khi bạn muốn chuyển sang một release mới hơn, các citation của sách sẽ trôi đi. Đây là quy trình re-sync chính
xác:

```bash
cd ~/Documents/learning/graphhopper
git fetch --tags
git checkout <new-tag>                 # e.g. 12.0 when it ships
git rev-parse --short HEAD             # record the new short SHA
```

Rồi re-verify chỉ mục **Key files** trong [`reference/glossary.md`](reference/glossary.md) trước tiên — nó là
xương sống. Với mỗi hàng, xác nhận symbol vẫn nằm ở đúng dòng được cite:

```bash
# spot-check a few load-bearing citations against the new checkout:
sed -n '460,469p' core/src/main/java/com/graphhopper/util/GHUtility.java        # calcEdgeWeight choke
sed -n '295p'     core/src/main/java/com/graphhopper/routing/AbstractBidirCHAlgo.java  # CH upward rule
sed -n '225,244p' reader-gtfs/src/main/java/com/graphhopper/gtfs/MultiCriteriaLabelSetting.java  # dominates
```

Nếu một symbol đã dời chỗ, cập nhật `file:line` của nó trong glossary và trong chương cite nó, đồng thời cập nhật
tag `PINNED` + short SHA inline trong `site_src/build_site.py` và trong Goal callout của mọi chương. Rồi rebuild:

```bash
cd ~/Documents/learning/graphhopper-book
python3 site_src/build_site.py         # → 11 pages + handbook.html
```

> 🧠 **Mental model:** *cấu trúc* của GraphHopper — import/store/query/shape, họ algorithm, hệ custom-model +
> encoded-value, label-setting cho transit, HMM matcher — ổn định đến ngạc nhiên qua các release. Re-pin gần như
> không bao giờ làm mất hiệu lực một *khái niệm*; nó chỉ xê dịch số dòng đôi chút. Đó chính là toàn bộ lý do học
> engine từ source: tấm bản đồ sống sót qua mỗi lần bump version.

## 8.5 Lab 8 — the capstone log

> 🧪 **Lab 8.** Goal: ghi lại ba capstone, một lần đọc PR, và một lượt re-verify. Ghi vào
> [`labs/lab08-pr.md`](labs/lab08-pr.md).

```bash
# after the three capstones, re-verify against a fresh checkout (or the current pin):
cd ~/Documents/learning/graphhopper
git describe --tags && git rev-parse --short HEAD
# then work through the PR-reading questions in §8.3 against a real merged PR.
```

**Expected:** ba capstone hoàn tất (custom `bus` profile re-route được; ba isochrone lồng nhau render ra; một
hành trình từ GTFS thật có transfer trả về); một merged PR được đọc với ba câu trả lời khớp ý đồ; và một lượt
re-verify xác nhận (hoặc chỉnh lại) một nhúm citation trong glossary.

## 8.6 Checkpoint

1. Profile `bus` của bạn tránh motorway và cầu tải nhẹ. Nó đọc hai encoded value nào, và vì sao nó phải chạy
   ngoài fast path của CH?
2. Vì sao một isochrone là một *cây* shortest-path, và vì sao polygon 15 phút bao trọn polygon 5 phút?
3. Đọc một PR từ con số không, ba câu hỏi nào bạn trả lời từ *diff* trước khi đọc phần mô tả?
4. Sau khi re-pin sang một tag mới, file duy nhất nào trong sách này bạn re-verify *đầu tiên*, và vì sao?
5. Cái gì sống sót nguyên vẹn qua một lần bump version — số dòng, hay mental model? Điều đó nói lên gì về cách học
   một codebase?

> Nếu capstone nào còn lung lay, đọc lại chương nó dựa vào (1→§4, 2→§7.5, 3→§5.5).

## 🔌 Connect to your past (you can now read your own routing stack)

Bạn bắt đầu cuốn sách này để có một baseline vững hơn về map technology và tìm đường cho BusMap, VinBus, và
ride-hailing. Giờ bạn có hơn cả một baseline: bạn trace được một route request từ HTTP tới algorithm rồi ngược
lại (Ch 1), giải thích được cái graph mà bản đồ hoá thành (Ch 2), chọn được đúng shortest-path algorithm cho một
đánh đổi latency/độ linh hoạt (Ch 3), định hình route bằng custom model cho fleet của mình (Ch 4), đọc được một
transit journey planner như production code (Ch 5), tái dựng được chuyến đi thật của một tài xế từ GPS (Ch 6), và
gọi tên được đúng object cùng endpoint mà app của bạn tiêu thụ (Ch 7). Lần tới khi một quyết định về routing nổi
lên ở chỗ làm — "vì sao ETA này sai?", "làm sao cho bus tránh con phố này?", "tính quãng đường chuyến đi từ GPS
thế nào?" — bạn sẽ không với tay tới trực giác. Bạn sẽ với tay tới file và dòng. Đó chính là toàn bộ lý do đọc từ
source.

*A RumitX publication · [rumitx.com](https://rumitx.com) · maps, routing & human-centric mobility.*
