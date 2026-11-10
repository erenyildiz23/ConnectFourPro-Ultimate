// =============================================================================
// ApiResponse.cs - Connect Four Pro Ultimate
// REST yaniti (ApiClient geri cagrilarina verilir)
// =============================================================================
//
// Unity'den bagimsizdir; tests/csharp altinda sahte ApiClient ile kullanilir.

namespace ConnectFourPro.Net
{
    public sealed class ApiResponse
    {
        /// <summary>HTTP durum kodu; baglanti kurulamadiysa 0.</summary>
        public long Status;
        public string Body;
        public bool NetworkError => Status == 0;
        public bool Ok => Status >= 200 && Status < 300;

        public object ParseBody()
        {
            try
            {
                return string.IsNullOrEmpty(Body) ? null : Json.Parse(Body);
            }
            catch (JsonException)
            {
                return null;
            }
        }

        public JsonObject BodyObject => JsonObject.From(ParseBody());
    }
}
