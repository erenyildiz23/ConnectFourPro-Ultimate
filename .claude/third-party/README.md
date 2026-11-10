# Üçüncü taraf skill'ler

`.claude/skills/` altındaki skill'ler bu depoda yazılmadı; aşağıdaki kaynaklardan kopyalandı.
Claude Code bu klasördeki skill'leri oturum başında otomatik bulur.

| Kaynak | Commit | Lisans | Kurulan | Değişiklik |
|---|---|---|---|---|
| [gamedev-skills/awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills) | `dcf3bbb` (2026-11-10) | Apache-2.0 — `gamedev-skills-LICENSE`, `gamedev-skills-NOTICE` | `router` + 77 skill (aşağıdaki liste) | Yok; dosyalar birebir kopya |
| [ckorhonen/claude-skills](https://github.com/ckorhonen/claude-skills) | `947001b` (2026-09-26) | MIT — `ckorhonen-claude-skills-LICENSE` | `skill-finder` | **Değiştirildi** (aşağıda) |

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

## skill-finder'da yapılan değişiklik

Arama ve sıralama adımları aynı. Değişen:

- Kurulum ve yeni skill oluşturma artık kullanıcının açık onayını gerektirir.
- Aday skill önerilmeden önce tüm dosyaları okunur ve kullanıcıya kaynağı, lisansı, betiklerinin
  ne yaptığı ve riskleri bildirilir.
- Varsayılan kurulum, incelenen dosyaların incelenen commit'ten kopyalanmasıdır; `npx
  claude-plugins` yalnızca kullanıcı isterse kullanılır.
- Kayıt defterine yalnızca genel anahtar sözcükler gönderilir.
- Açıklama satırındaki "AUTOMATICALLY activates" ve "auto-installs" ifadeleri kaldırıldı.

## Güncelleme

Yeni sürüme geçerken kaynak depoyu klonlayın, değişen dosyaları okuyun, sonra skill klasörlerini
yeniden kopyalayın ve bu tablodaki commit'i güncelleyin. `skill-finder` elle uyarlanmıştır;
üzerine yazmayın.

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
