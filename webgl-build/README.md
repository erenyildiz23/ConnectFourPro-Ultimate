Bu klasör Docker imajına gömülecek Unity WebGL derlemesi içindir.

CI (`.github/workflows/docker-image.yml`) derlemeyi buraya indirip imajı öyle oluşturur.
Elle imaj oluşturacaksanız `unity/Build/WebGL` içeriğini buraya kopyalayın. Klasör boşsa
imaj yine çalışır; yalnızca `/play/` adresi 404 döner.
