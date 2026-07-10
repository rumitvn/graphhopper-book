#!/usr/bin/env python3
"""Per-book configuration for the GraphHopper Internals Handbook.

This is the ONLY file that differs between RumitX books. engine.py next to it is
byte-identical everywhere.

Register note (see learning/CLAUDE.md): chapter titles stay in English in both
locales — they name the technology, they match each chapter's H1, and the reader
meets them in the source. Vietnamese carries the prose: descriptions, hero copy,
and UI chrome.
"""

REPO_URL = "https://github.com/rumitvn/graphhopper-book"   # the book's own repo (labs/ blob links)
UPSTREAM = "https://github.com/graphhopper/graphhopper"     # the engine we study
UPSTREAM_NAME = "graphhopper/graphhopper"
PINNED = "11.0"                                             # pinned tag
UPSTREAM_PINNED = UPSTREAM + "/tree/" + PINNED

# code-fence languages this book uses beyond the engine's defaults
LANG_LABEL_EXTRA = {
    "java": "Java", "kotlin": "Kotlin", "kt": "Kotlin", "swift": "Swift",
    "objc": "Objective-C", "ts": "TypeScript", "typescript": "TypeScript",
    "cmake": "CMake", "make": "Makefile",
    "glsl": "GLSL", "comp": "GLSL", "metal": "Metal", "asm": "asm",
    "toml": "TOML", "yaml": "YAML", "yml": "YAML", "xml": "XML",
    "properties": "properties", "http": "HTTP", "sql": "SQL",
    "protobuf": "Protobuf", "proto": "Protobuf",
}

# (number, stem, flag, {locale: (title, description)})
CHAPTERS = [
    ("00", "00-environment-and-java-refresher", "Foundation", {
        "en": ("Environment & Java Refresher",
               "Get a tree you can read: clone GraphHopper pinned to 11.0, build the modules with Maven, run the routing server on a small city extract, and refresh the idioms the codebase leans on — the builder API, GHRequest/GHResponse, encoded values, and memory-mapped DataAccess storage."),
        "vi": ("Environment & Java Refresher",
               "Dựng một cây thư mục bạn đọc được: clone GraphHopper pin ở 11.0, build các module bằng Maven, chạy routing server trên một extract thành phố nhỏ, và ôn lại các idiom mà codebase này dựa vào — builder API, GHRequest/GHResponse, encoded values, và storage DataAccess memory-mapped."),
    }),
    ("01", "01-mental-model-and-the-repo-map", "Foundation", {
        "en": ("Mental Model & the Repo Map",
               "A routing engine is import → store → query → shape. The N-layer mental model, the module map, and one real end-to-end trace: a single /route?point=A&point=B request from the HTTP resource down to the algorithm and back out as a ResponsePath."),
        "vi": ("Mental Model & the Repo Map",
               "Một routing engine là import → store → query → shape. Mental model N-tầng, bản đồ module, và một trace thật từ đầu đến cuối: một request /route?point=A&point=B đi từ HTTP resource xuống tận algorithm rồi quay ra thành một ResponsePath."),
    }),
    ("02", "02-the-graph-map-to-network", "Core", {
        "en": ("The Graph — turning a map into a routable network",
               "The substrate every algorithm walks: how OSMReader turns an .osm.pbf into a BaseGraph of nodes and edges, how EdgeIterator sweeps a node's neighbours, how DataAccess stores it all in flat arrays (RAM or memory-mapped), and how turn restrictions live on the graph."),
        "vi": ("The Graph — turning a map into a routable network",
               "Nền tảng mà mọi algorithm bước lên: cách OSMReader biến một .osm.pbf thành BaseGraph gồm node và edge, cách EdgeIterator quét các neighbour của một node, cách DataAccess lưu tất cả trong các mảng phẳng (RAM hoặc memory-mapped), và turn restriction sống trên graph ra sao."),
    }),
    ("03", "03-shortest-path-algorithms", "★ Flagship", {
        "en": ("The Shortest-Path Algorithm Family",
               "The heart of the engine in four case studies: plain Dijkstra and the pluggable Weighting; A* and the bidirectional meeting condition; Contraction Hierarchies and why it is ~1000× faster; and Landmarks/ALT for when you cannot precompute. This is where route-finding earns its name."),
        "vi": ("The Shortest-Path Algorithm Family",
               "Trái tim của engine trong bốn case study: Dijkstra thuần và Weighting cắm-được; A* và điều kiện gặp nhau của bidirectional; Contraction Hierarchies và vì sao nó nhanh gấp ~1000×; và Landmarks/ALT cho khi bạn không thể precompute trước. Đây là chỗ route-finding xứng với cái tên của nó."),
    }),
    ("04", "04-profiles-weighting-custom-models", "Core", {
        "en": ("Profiles, Weighting & Custom Models",
               "How you actually shape a route: Profiles, the CustomModel expression DSL and CustomWeighting, and the EncodedValue system (EncodingManager) that packs per-edge attributes — road class, max weight, access — into bits the weighting reads. Where bus-only and vehicle constraints live."),
        "vi": ("Profiles, Weighting & Custom Models",
               "Cách bạn thực sự nắn một route: Profile, DSL biểu thức CustomModel cùng CustomWeighting, và hệ EncodedValue (EncodingManager) đóng gói các thuộc tính per-edge — road class, max weight, access — thành các bit mà weighting đọc. Nơi các ràng buộc bus-only và vehicle nằm."),
    }),
    ("05", "05-public-transit-gtfs-raptor", "Application", {
        "en": ("Public Transit — GTFS & RAPTOR",
               "The transit engine: how GtfsReader ingests a GTFS feed into a time-expanded PtGraph, how MultiCriteriaLabelSetting does RAPTOR-style multi-criteria search (arrival time, transfers, walking), and how GTFS-realtime updates fold in. The chapter that maps straight onto BusMap and VinBus."),
        "vi": ("Public Transit — GTFS & RAPTOR",
               "Engine transit: cách GtfsReader nạp một GTFS feed vào một PtGraph time-expanded, cách MultiCriteriaLabelSetting chạy search đa tiêu chí kiểu RAPTOR (giờ đến, số lần chuyển, đi bộ), và cách các update GTFS-realtime gộp vào. Chương ánh xạ thẳng lên BusMap và VinBus."),
    }),
    ("06", "06-map-matching", "Application", {
        "en": ("Map-Matching — snapping GPS to roads",
               "Turning a noisy GPS trace into the road path a driver actually took: the Newson–Krumm Hidden Markov Model, candidate snaps as emission probabilities, routing between candidates as transition probabilities, and the Viterbi pass that picks the most likely sequence. The ride-hailing pillar."),
        "vi": ("Map-Matching — snapping GPS to roads",
               "Biến một GPS trace nhiễu thành đúng đường mà tài xế thật sự đã đi: Hidden Markov Model Newson–Krumm, các snap ứng viên như emission probability, việc routing giữa các ứng viên như transition probability, và lượt Viterbi chọn ra chuỗi khả dĩ nhất. Trụ cột của ride-hailing."),
    }),
    ("07", "07-navigation-isochrones-web", "Application", {
        "en": ("Navigation, Isochrones & the Web/Tiles Surface",
               "How the engine reaches the app: turning an edge sequence into turn-by-turn Instructions, the route / matrix / isochrone / nearest / vector-tile HTTP endpoints, and the ResponsePath + PathDetail response model that a map UI and an ETA surface consume."),
        "vi": ("Navigation, Isochrones & the Web/Tiles Surface",
               "Cách engine chạm tới app: biến một chuỗi edge thành Instruction turn-by-turn, các endpoint HTTP route / matrix / isochrone / nearest / vector-tile, và mô hình response ResponsePath + PathDetail mà một map UI và một mặt ETA tiêu thụ."),
    }),
    ("08", "08-capstone-and-staying-current", "Mastery", {
        "en": ("Capstone & Staying Current",
               "Add a custom profile, build an isochrone, run a transit query on a real city's GTFS, read a merged GraphHopper PR unaided, and re-sync this book after you re-pin to a newer tag."),
        "vi": ("Capstone & Staying Current",
               "Thêm một custom profile, dựng một isochrone, chạy một transit query trên GTFS của một thành phố thật, đọc một PR GraphHopper đã merge mà không cần trợ giúp, và re-sync cuốn sách này sau khi bạn re-pin sang một tag mới hơn."),
    }),
]

_UI_EN = {
    "chapters": "Chapters", "reference": "Reference", "glossary": "Glossary & Index",
    "glossary_short": "Glossary", "repo": "GitHub repo", "on_this_page": "On this page",
    "previous": "← Previous", "next": "Next →", "home": "Handbook", "chapter": "Chapter",
    "read_chapter": "Read chapter →", "pinned": "pinned", "single_file": "single file",
    "grounded_in": "grounded in",
    "a_publication": 'A <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> '
                     'publication · maps, routing &amp; human-centric mobility',
}
_UI_VI = {
    "chapters": "Chương", "reference": "Tham khảo", "glossary": "Glossary & Index",
    "glossary_short": "Glossary", "repo": "GitHub repo", "on_this_page": "Trong trang này",
    "previous": "← Trước", "next": "Tiếp →", "home": "Handbook", "chapter": "Chương",
    "read_chapter": "Đọc chương →", "pinned": "pinned", "single_file": "một file",
    "grounded_in": "neo vào",
    "a_publication": 'Một ấn phẩm của <a href="https://rumitx.com" target="_blank" rel="noopener">RumitX</a> '
                     '· maps, routing &amp; human-centric mobility',
}

COPY = {
    "en": {
        "brand": "GraphHopper Internals Handbook",
        "landing_title": "GraphHopper Internals Handbook · maps & route-finding from the source",
        "meta_description": "A from-the-source handbook on graphhopper/graphhopper: the graph model, "
                            "Dijkstra / A* / Contraction Hierarchies / Landmarks, custom-model weighting, "
                            "GTFS & RAPTOR transit, map-matching, and the routing web API.",
        "kicker": "● GraphHopper · open-source routing engine · maps &amp; route-finding",
        "h1": "Find the route,<br>not just draw the map.",
        "sub": f"A from-the-source handbook that turns <code>{UPSTREAM_NAME}</code> — the open-source "
               f"engine that powers routing, transit and navigation for real mobility apps — into "
               f"something you genuinely understand. Follow one <code>/route</code> request from the HTTP "
               f"API, into the <code>BaseGraph</code>, through <code>Dijkstra</code> → <code>A*</code> → "
               f"<code>Contraction Hierarchies</code>, across <code>GTFS</code>/<code>RAPTOR</code> "
               f"transit and GPS <code>map-matching</code> — every step grounded in real "
               f"<code>file:line</code> citations.",
        "chips": ["9 chapters · 1 flagship", f"pinned <b>{PINNED}</b>",
                  "OSM → graph → <b>CH → route</b>", "reconnects <b>BusMap / VinBus &amp; ride-hailing</b>"],
        "cta_start": "Start with Chapter 0 →",
        "cta_flagship": "Jump to the flagship ★",
        "label_curriculum": "The curriculum — depth weighted toward the shortest-path algorithms",
        "label_howto": "How to use this book",
        "how_to_use": [
            {"kicker": "METHOD", "h3": "Read with the source open",
             "p": f"Every chapter cites exact <code>file:line</code> locations in a local clone pinned "
                  f"to {PINNED}. Keep <code>graphhopper</code> open beside each page. Each chapter ends "
                  f"with checkpoint questions and a “Connect to your past” sidebar bridging to transit "
                  f"apps (BusMap, VinBus) and ride-hailing routing."},
            {"kicker": "SHAPE", "h3": "Why → model → source → lab",
             "p": "Concept, then a mental model + ASCII diagram, then a guided source read, then a "
                  "hands-on lab you run against your own local GraphHopper server with a stated "
                  "expected result."},
        ],
        "footer_note": "maps &amp; route-finding, from the source",
        "handbook_sub": f"The complete book in one file — the <code>BaseGraph</code>, the shortest-path "
                        f"family (<code>Dijkstra</code>, <code>A*</code>, <code>Contraction "
                        f"Hierarchies</code>, <code>Landmarks</code>), custom-model weighting, "
                        f"<code>GTFS</code>/<code>RAPTOR</code> transit, GPS <code>map-matching</code>, "
                        f"and the routing web API. Grounded in <code>{UPSTREAM_NAME}</code> @ "
                        f"<code>{PINNED}</code>. Use the rail to jump; press the printer icon to save "
                        f"as PDF.",
        "ui": _UI_EN,
    },
    "vi": {
        "brand": "GraphHopper Internals Handbook",
        "landing_title": "GraphHopper Internals Handbook · đọc maps & route-finding từ source",
        "meta_description": "Cuốn sách đọc thẳng từ source về graphhopper/graphhopper: graph model, "
                            "Dijkstra / A* / Contraction Hierarchies / Landmarks, custom-model weighting, "
                            "GTFS & RAPTOR transit, map-matching, và routing web API.",
        "kicker": "● GraphHopper · routing engine mã nguồn mở · maps &amp; route-finding",
        "h1": "Tìm ra route,<br>không chỉ vẽ cái map.",
        "sub": f"Một cuốn sách đọc thẳng từ source, biến <code>{UPSTREAM_NAME}</code> — engine mã nguồn "
               f"mở đứng sau routing, transit và navigation của các app mobility thật — thành thứ bạn "
               f"thực sự hiểu. Theo một request <code>/route</code> từ HTTP API, vào "
               f"<code>BaseGraph</code>, qua <code>Dijkstra</code> → <code>A*</code> → "
               f"<code>Contraction Hierarchies</code>, băng qua transit <code>GTFS</code>/"
               f"<code>RAPTOR</code> và <code>map-matching</code> GPS — mỗi bước đều neo vào các trích "
               f"dẫn <code>file:line</code> thật.",
        "chips": ["9 chương · 1 flagship", f"pinned <b>{PINNED}</b>",
                  "OSM → graph → <b>CH → route</b>", "nối lại <b>BusMap / VinBus &amp; ride-hailing</b>"],
        "cta_start": "Bắt đầu từ Chương 0 →",
        "cta_flagship": "Nhảy tới chương flagship ★",
        "label_curriculum": "Lộ trình — chiều sâu dồn vào nhóm shortest-path algorithm",
        "label_howto": "Dùng cuốn sách này thế nào",
        "how_to_use": [
            {"kicker": "PHƯƠNG PHÁP", "h3": "Đọc với source mở sẵn bên cạnh",
             "p": f"Mỗi chương trích dẫn chính xác vị trí <code>file:line</code> trong một bản clone "
                  f"local đã pin ở {PINNED}. Hãy mở <code>graphhopper</code> bên cạnh từng trang. Cuối "
                  f"mỗi chương là các câu hỏi checkpoint và một sidebar “Connect to your past” bắc cầu "
                  f"sang các app transit (BusMap, VinBus) và routing cho ride-hailing."},
            {"kicker": "CẤU TRÚC", "h3": "Vì sao → model → source → lab",
             "p": "Khái niệm trước, rồi tới mental model kèm ASCII diagram, rồi một lượt đọc source có "
                  "dẫn đường, rồi một lab bạn tự chạy trên chính GraphHopper server local của mình với "
                  "kết quả mong đợi được nói rõ."},
        ],
        "footer_note": "maps &amp; route-finding, đọc từ source",
        "handbook_sub": f"Trọn cuốn sách trong một file — <code>BaseGraph</code>, nhóm shortest-path "
                        f"(<code>Dijkstra</code>, <code>A*</code>, <code>Contraction Hierarchies</code>, "
                        f"<code>Landmarks</code>), custom-model weighting, transit <code>GTFS</code>/"
                        f"<code>RAPTOR</code>, <code>map-matching</code> GPS, và routing web API. Neo vào "
                        f"<code>{UPSTREAM_NAME}</code> @ <code>{PINNED}</code>. Dùng thanh rail để nhảy "
                        f"chương; bấm icon máy in để lưu PDF.",
        "ui": _UI_VI,
    },
}
