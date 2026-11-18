// Satranc saati gosterimi: kalan saniye -> "m:ss" (orn. 180 -> "3:00", 9 -> "0:09").
// Saf C#: UnityEngine kullanmaz, testlenebilir.
using System.Globalization;

namespace ConnectFourPro.Game
{
    public static class ClockFormat
    {
        /// <summary>Kalan tam saniyeyi "dakika:saniye" yazar; eksi deger "0:00" olur.</summary>
        public static string Format(int seconds)
        {
            if (seconds < 0)
                seconds = 0;
            return (seconds / 60) + ":" + (seconds % 60).ToString("00", CultureInfo.InvariantCulture);
        }
    }
}
