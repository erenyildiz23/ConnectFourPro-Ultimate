// =============================================================================
// Json.cs - Connect Four Pro Ultimate
// Kucuk, bagimliliksiz JSON okuyucu/yazici
// =============================================================================
//
// Neden JsonUtility degil? Sunucunun gonderdigi bazi alanlar sozluk
// ('bitboards': {"1": ..., "2": ...}) veya null olabilir; JsonUtility bunlari
// okuyamaz. Bu sinif Unity'den bagimsizdir ve tests/csharp altinda test edilir.
//
// Okunan degerler: Dictionary<string, object>, List<object>, string, long
// (tam sayilar), double (ondalikli), bool, null.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace ConnectFourPro.Net
{
    public sealed class JsonException : Exception
    {
        public JsonException(string message) : base(message)
        {
        }
    }

    public static class Json
    {
        // ------------------------------------------------------------------
        // Okuma
        // ------------------------------------------------------------------

        public static object Parse(string text)
        {
            if (text == null)
                throw new JsonException("Bos JSON");
            var p = new Parser(text);
            p.SkipWhitespace();
            object value = p.ParseValue();
            p.SkipWhitespace();
            if (!p.AtEnd)
                throw new JsonException("JSON sonunda fazladan karakter: konum " + p.Position);
            return value;
        }

        private sealed class Parser
        {
            private readonly string _s;
            private int _i;

            public Parser(string s)
            {
                _s = s;
            }

            public bool AtEnd => _i >= _s.Length;
            public int Position => _i;

            public void SkipWhitespace()
            {
                while (_i < _s.Length && char.IsWhiteSpace(_s[_i]))
                    _i++;
            }

            private char Peek()
            {
                if (_i >= _s.Length)
                    throw new JsonException("Beklenmeyen JSON sonu");
                return _s[_i];
            }

            private void Expect(char c)
            {
                if (Peek() != c)
                    throw new JsonException($"'{c}' bekleniyordu, '{_s[_i]}' bulundu: konum {_i}");
                _i++;
            }

            public object ParseValue()
            {
                char c = Peek();
                switch (c)
                {
                    case '{': return ParseObject();
                    case '[': return ParseArray();
                    case '"': return ParseString();
                    case 't': ExpectWord("true"); return true;
                    case 'f': ExpectWord("false"); return false;
                    case 'n': ExpectWord("null"); return null;
                    default:
                        if (c == '-' || (c >= '0' && c <= '9'))
                            return ParseNumber();
                        throw new JsonException($"Gecersiz JSON karakteri '{c}': konum {_i}");
                }
            }

            private void ExpectWord(string word)
            {
                if (string.CompareOrdinal(_s, _i, word, 0, word.Length) != 0)
                    throw new JsonException($"'{word}' bekleniyordu: konum {_i}");
                _i += word.Length;
            }

            private Dictionary<string, object> ParseObject()
            {
                var result = new Dictionary<string, object>();
                Expect('{');
                SkipWhitespace();
                if (Peek() == '}')
                {
                    _i++;
                    return result;
                }
                while (true)
                {
                    SkipWhitespace();
                    string key = ParseString();
                    SkipWhitespace();
                    Expect(':');
                    SkipWhitespace();
                    result[key] = ParseValue();
                    SkipWhitespace();
                    if (Peek() == ',')
                    {
                        _i++;
                        continue;
                    }
                    Expect('}');
                    return result;
                }
            }

            private List<object> ParseArray()
            {
                var result = new List<object>();
                Expect('[');
                SkipWhitespace();
                if (Peek() == ']')
                {
                    _i++;
                    return result;
                }
                while (true)
                {
                    SkipWhitespace();
                    result.Add(ParseValue());
                    SkipWhitespace();
                    if (Peek() == ',')
                    {
                        _i++;
                        continue;
                    }
                    Expect(']');
                    return result;
                }
            }

            private string ParseString()
            {
                Expect('"');
                var sb = new StringBuilder();
                while (true)
                {
                    char c = Peek();
                    _i++;
                    if (c == '"')
                        return sb.ToString();
                    if (c != '\\')
                    {
                        sb.Append(c);
                        continue;
                    }
                    char e = Peek();
                    _i++;
                    switch (e)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'b': sb.Append('\b'); break;
                        case 'f': sb.Append('\f'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'u':
                            if (_i + 4 > _s.Length)
                                throw new JsonException("Eksik \\u kacisi");
                            sb.Append((char)int.Parse(_s.Substring(_i, 4), NumberStyles.HexNumber,
                                                      CultureInfo.InvariantCulture));
                            _i += 4;
                            break;
                        default:
                            throw new JsonException($"Gecersiz kacis '\\{e}': konum {_i}");
                    }
                }
            }

            private object ParseNumber()
            {
                int start = _i;
                bool isFloat = false;
                if (_s[_i] == '-')
                    _i++;
                while (_i < _s.Length)
                {
                    char c = _s[_i];
                    if (c >= '0' && c <= '9')
                        _i++;
                    else if (c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-')
                    {
                        isFloat = true;
                        _i++;
                    }
                    else
                        break;
                }
                string token = _s.Substring(start, _i - start);
                if (!isFloat && long.TryParse(token, NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out long l))
                    return l;
                if (double.TryParse(token, NumberStyles.Float, CultureInfo.InvariantCulture, out double d))
                    return d;
                throw new JsonException($"Gecersiz sayi '{token}'");
            }
        }

        // ------------------------------------------------------------------
        // Yazma
        // ------------------------------------------------------------------

        public static string Serialize(object value)
        {
            var sb = new StringBuilder();
            Write(sb, value);
            return sb.ToString();
        }

        private static void Write(StringBuilder sb, object value)
        {
            switch (value)
            {
                case null:
                    sb.Append("null");
                    break;
                case string s:
                    WriteString(sb, s);
                    break;
                case bool b:
                    sb.Append(b ? "true" : "false");
                    break;
                case int or long or short or byte or uint or ulong:
                    sb.Append(Convert.ToString(value, CultureInfo.InvariantCulture));
                    break;
                case float f:
                    sb.Append(f.ToString("R", CultureInfo.InvariantCulture));
                    break;
                case double d:
                    sb.Append(d.ToString("R", CultureInfo.InvariantCulture));
                    break;
                case IDictionary dict:
                {
                    sb.Append('{');
                    bool first = true;
                    foreach (DictionaryEntry kv in dict)
                    {
                        if (!first)
                            sb.Append(',');
                        first = false;
                        WriteString(sb, Convert.ToString(kv.Key, CultureInfo.InvariantCulture));
                        sb.Append(':');
                        Write(sb, kv.Value);
                    }
                    sb.Append('}');
                    break;
                }
                case IEnumerable list:
                {
                    sb.Append('[');
                    bool first = true;
                    foreach (object item in list)
                    {
                        if (!first)
                            sb.Append(',');
                        first = false;
                        Write(sb, item);
                    }
                    sb.Append(']');
                    break;
                }
                default:
                    WriteString(sb, value.ToString());
                    break;
            }
        }

        private static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20)
                            sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        else
                            sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }
    }

    /// <summary>
    /// Ayristirilmis JSON nesnesi uzerinde tip-guvenli okuma yardimcilari.
    /// Eksik veya yanlis tipli alanlarda varsayilan deger doner (sunucu sozlesmesi esnek).
    /// </summary>
    public sealed class JsonObject
    {
        private readonly Dictionary<string, object> _d;

        public JsonObject(Dictionary<string, object> d)
        {
            _d = d ?? new Dictionary<string, object>();
        }

        public static JsonObject From(object value) => new JsonObject(value as Dictionary<string, object>);

        public static JsonObject ParseObject(string json)
        {
            if (string.IsNullOrEmpty(json))
                return new JsonObject(null);
            return From(Json.Parse(json));
        }

        public bool Has(string key) => _d.ContainsKey(key);
        public bool IsNull(string key) => !_d.TryGetValue(key, out object v) || v == null;
        public object Raw(string key) => _d.TryGetValue(key, out object v) ? v : null;
        public IEnumerable<string> Keys => _d.Keys;

        public string GetString(string key, string fallback = null)
        {
            if (!_d.TryGetValue(key, out object v) || v == null)
                return fallback;
            return v as string ?? Convert.ToString(v, CultureInfo.InvariantCulture);
        }

        public long GetLong(string key, long fallback = 0)
        {
            if (!_d.TryGetValue(key, out object v))
                return fallback;
            return v switch
            {
                long l => l,
                double d => (long)d,
                bool b => b ? 1 : 0,
                string s when long.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out long p) => p,
                _ => fallback,
            };
        }

        public int GetInt(string key, int fallback = 0) => (int)GetLong(key, fallback);

        /// <summary>Alan yoksa veya null ise null.</summary>
        public int? GetNullableInt(string key)
        {
            if (!_d.TryGetValue(key, out object v) || v == null)
                return null;
            return v is long || v is double ? (int?)GetLong(key) : null;
        }

        public bool GetBool(string key, bool fallback = false)
        {
            if (!_d.TryGetValue(key, out object v))
                return fallback;
            return v is bool b ? b : fallback;
        }

        public JsonObject GetObject(string key) => From(Raw(key));

        public List<object> GetArray(string key) => Raw(key) as List<object> ?? new List<object>();

        public List<int> GetIntList(string key)
        {
            var result = new List<int>();
            foreach (object o in GetArray(key))
                if (o is long l)
                    result.Add((int)l);
                else if (o is double d)
                    result.Add((int)d);
            return result;
        }

        public List<JsonObject> GetObjectList(string key)
        {
            var result = new List<JsonObject>();
            foreach (object o in GetArray(key))
                result.Add(From(o));
            return result;
        }
    }
}
