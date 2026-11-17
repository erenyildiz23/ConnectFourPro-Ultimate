# Üçüncü taraf skill'ler

`.claude/skills/` altındaki skill'ler bu depoda yazılmadı; aşağıdaki kaynaklardan kopyalandı.
Claude Code bu klasördeki skill'leri oturum başında otomatik bulur.

| Kaynak | Commit | Lisans | Kurulan | Değişiklik |
|---|---|---|---|---|
| [gamedev-skills/awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) | `dcf3bbb` (2026-11-10) | Apache-2.0 — `gamedev-skills-LICENSE`, `gamedev-skills-NOTICE` | `router` + 77 skill (aşağıdaki liste) | Yok; dosyalar birebir kopya |
| [ckorhonen/claude-skills](https://github.com/ckorhonen/claude-skills) | `947001b` (2026-09-26) | MIT — `ckorhonen-claude-skills-LICENSE` | `skill-finder` | **Değiştirildi** (aşağıda) |
| [donchitos/claude-code-game-studios](https://github.com/donchitos/claude-code-game-studios) | `abc0de7` (2026-11-09) | MIT — `donchitos-claude-code-game-studios-LICENSE` | 9 skill (aşağıdaki liste) | **Değiştirildi** (aşağıda) |

## Kurulum öncesi denetim

Kurulmadan önce 225 dosyanın tamamı okundu (gizli talimat, uzaktan kod çalıştırma, kimlik
bilgisi sızdırma, yıkıcı komut ve gizli Unicode karakter arandı); bulunan her şüpheli nokta
ayrı bir incelemeyle doğrulandı.

- **gamedev-skills:** engelleyici bulgu yok. Betiklerin hiçbiri ağa çıkmıyor.
  - Beş proje denetleyicisi (`check_unity_project.py`, `check_godot_project.py`,
    `check_defold_project.py`, `check_steam_build.py`, `check_ebitengine.py`) yalnızca okur ve
    rapor yazdırır.
  - `new_game.py` hedef klasöre başlangıç projesi kopyalar; `build_preview_sheet.py` verilen
    `--out` yoluna tek bir görsel yazar; `package_macos_app.py` `lipo` çalıştırır ve `--force`
    ile mevcut `.app` paketini siler.
  - Dikkat edilecek tek nokta: `unity-csharp-scripting`, denetleyiciyi çalıştırıp "her ERROR'u
    düzelt" der. Bu `.meta` dosyalarını taşımaya veya silmeye götürebilir; düzeltmeden önce
    kullanıcıya sorulmalı.
  - `itch-publish` ve `steam-publish` hesap girişi ve yayın yükleme adımları içerir; bunlar
    kullanıcı onayı olmadan yapılmamalı.
- **skill-finder:** özgün hali, topluluk kayıt defterinden (`claude-plugins.dev`) skill arayıp
  kullanıcıya sormadan `npx claude-plugins` ile kurmayı ve hemen kullanmayı söylüyordu; tek
  ölçüt yıldız ve kurulum sayısıydı. İncelenmemiş talimatların otomatik kurulması anlamına
  geldiği için bu haliyle kurulmadı.

- **claude-code-game-studios:** depodaki 78 skill'in açıklaması tarandı; seçilen 9 skill'in
  tek dosyası (`SKILL.md`, toplam 2.645 satır) baştan sona okundu. Gizli talimat, HTML yorumu,
  base64, uzaktan kod indirme/çalıştırma, kimlik bilgisi okuma, yıkıcı git komutu ve kendi
  başına push/PR/giriş talimatı yok. Görünmez Unicode taraması temiz: ASCII dışı karakterler
  yalnızca tire, ok, orta nokta, üç nokta, Δ ve üç uyarı emojisi (⚠ ile gelen VS-16 dahil).
  - **Engelleyici bulgu (düzeltildi):** her skill'in ilk satırı
    `` !`bash "${CLAUDE_SKILL_DIR}/../../hooks/yaml-helper.sh" resolve_config …` `` idi. Bu
    satır skill yüklenir yüklenmez kabuk komutu çalıştırır; `allowed-tools` da o betiğe Bash
    izni veriyordu. Betik kurulmadı (`.claude/hooks/` bu projede yok), ama yol proje
    içine çözüldüğü için ileride oraya konan bir dosya sorulmadan çalışırdı.
  - `write-changelog` yüklenince `git log --oneline -30` ve `git tag --list` çalıştırır
    (`!` satırları). Salt okunur, yerel; olduğu gibi bırakıldı.
  - Hepsi `project.yaml`, `.claude/docs/*`, `production/` ve `design/` klasörlerine, stüdyo
    ajanlarına (`security-engineer`, `creative-director`) ve kurulmayan skill'lere
    (`/gate-check`, `/hotfix`, `/team-release`, `/smoke-check` …) atıf yapar. Bunlar yok;
    eklenen not bu durumda ne yapılacağını söyler.
  - Rapor dosyalarını `production/...` ve `docs/...` altına, **sorduktan sonra** yazarlar;
    kabul edilirse bu klasörler oluşur.
  - `security-audit`: grep kalıpları Godot/Unity/Unreal içindir, Python/Flask-SocketIO
    sunucusu için kalıp yok; ilgili kategoriler "NOT ASSESSED" çıkabilir. Sunucu tarafı
    (sunucu otoritesi, hız sınırı, girdi doğrulama) elle kontrol edilmeli. Gerçek bir sızma
    testinin yerini tutmaz (skill da bunu söylüyor).
  - `bug-report verify` testi `commands.test` ile çalıştırır; bu anahtar yok, test komutu
    kullanıcıya sorulmalı.
  - `launch-checklist` `disable-model-invocation: true` taşır; yalnızca `/launch-checklist`
    ile açılır.
- **Kurulmayanlar:** bu depodan `hooks`, `agents`, `rules`, `scripts`, `docs`, `genres`,
  `engines`, `settings.json`, `statusline.sh` ve `CLAUDE.md` bilerek kurulmadı. Hook'lar ve
  ayarlar sahibi okumadan kod çalıştırır ya da Claude'un davranışını değiştirir; ajanlar ve
  kurallar o deponun stüdyo iş akışına bağlıdır.

## skill-finder'da yapılan değişiklik

Arama ve sıralama adımları aynı. Değişen:

- Kurulum ve yeni skill oluşturma artık kullanıcının açık onayını gerektirir.
- Aday skill önerilmeden önce tüm dosyaları okunur ve kullanıcıya kaynağı, lisansı, betiklerinin
  ne yaptığı ve riskleri bildirilir.
- Varsayılan kurulum, incelenen dosyaların incelenen commit'ten kopyalanmasıdır; `npx
  claude-plugins` yalnızca kullanıcı isterse kullanılır.
- Kayıt defterine yalnızca genel anahtar sözcükler gönderilir.
- Açıklama satırındaki "AUTOMATICALLY activates" ve "auto-installs" ifadeleri kaldırıldı.

## claude-code-game-studios skill'lerinde yapılan değişiklik

Dokuz `SKILL.md` dosyasında aynı üç değişiklik yapıldı; gövde metni başka yerde aynı:

- `` !`bash "${CLAUDE_SKILL_DIR}/../../hooks/yaml-helper.sh" resolve_config --keys …` ``
  satırı silindi; yerine "Installed outside Claude Code Game Studios" diye başlayan yedi
  satırlık bir not kondu (eksik yapılandırma ve dosyalarda ne yapılacağı, ajan yerine işi
  oturumun kendisinin yapması, yalnızca kurulu skill'lerin önerilmesi).
- `allowed-tools` satırından `Bash(bash "*/.claude/skills/<ad>/../../hooks/yaml-helper.sh"
  resolve_config *)` izni çıkarıldı.
- `model:` satırı kaldırıldı; skill oturumun modeliyle çalışır.

## Güncelleme

Yeni sürüme geçerken kaynak depoyu klonlayın, değişen dosyaları okuyun, sonra skill klasörlerini
yeniden kopyalayın ve bu tablodaki commit'i güncelleyin. `skill-finder` ve
claude-code-game-studios skill'leri elle uyarlanmıştır; üzerine yazmayın, değişikliği yeniden
uygulayın.

## Kullanılmayan motorları kaldırmak

Bu proje Unity ve pygame kullanıyor. Diğer motorların skill'leri (`godot-*`, `unreal-*`,
`roblox-*`, `ebitengine-game`, `phaser-*`, `pixijs-rendering`, `threejs-*`, `bevy-ecs`,
`love2d-core`, `defold-core`) bu projede kullanılmaz ve silinebilir.

## gamedev-skills listesi

- **Yönlendirici:** `router`
- **Unity:** `unity-animation`, `unity-build-pipeline`, `unity-csharp-scripting`,
  `unity-input-system`, `unity-navmesh`, `unity-physics`, `unity-scriptableobjects`,
  `unity-tilemap-2d`
- **Disiplinler:** `ai-behavior-trees-utility-ai`, `audio-design`, `camera-systems`,
  `create-game-assets`, `dialogue-systems`, `game-ai`, `game-feel`, `game-ui-ux`,
  `input-systems`, `level-design`, `performance-optimization`, `physics-tuning`,
  `procedural-gen`, `save-systems`, `shader-programming`
- **Türler:** `card-game`, `fps-shooter`, `platformer`, `puzzle`, `roguelike`, `rpg`,
  `survival-crafting`, `tower-defense`, `visual-novel`
- **İş akışları:** `game-jam`, `itch-publish`, `prototype-fast`, `steam-publish`
- **Godot:** `godot-2d-movement`, `godot-3d-essentials`, `godot-animation`, `godot-audio`,
  `godot-csharp`, `godot-export`, `godot-gdscript`, `godot-gdscript-headless-testing`,
  `godot-multiplayer`, `godot-nodes-scenes`, `godot-physics`, `godot-resources`,
  `godot-shaders`, `godot-signals-groups`, `godot-tilemap`, `godot-ui-control`
- **Unreal:** `unreal-behavior-trees`, `unreal-blueprints`, `unreal-cpp-gameplay`,
  `unreal-enhanced-input`, `unreal-niagara`, `unreal-packaging`
- **Web motorları:** `phaser-arcade-physics`, `phaser-core`, `pixijs-rendering`,
  `threejs-gltf-loading`, `threejs-materials-lighting`, `threejs-scene-setup`
- **Diğer motorlar:** `bevy-ecs`, `defold-core`, `ebitengine-game`, `love2d-core`,
  `pygame-core`, `roblox-characters`, `roblox-datastores`, `roblox-luau`,
  `roblox-networking`, `roblox-physics`, `roblox-simulator-economy`,
  `roblox-studio-workflow`, `roblox-ui`

## claude-code-game-studios listesi

- **Yayın:** `release-checklist` (itch.io katmanı dahil), `launch-checklist`
- **Güvenlik:** `security-audit`
- **Hata takibi:** `bug-report`, `bug-triage`
- **Sürüm notları:** `write-changelog`, `patch-notes`
- **Test:** `playtest-report`, `soak-test`
