using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

/// <summary>
/// 迅雷 AI 片库离线 Demo 启动器。
///
/// 评委解压提交包后，只需双击 EXE。启动器会在本机回环地址创建静态文件服务，
/// 自动寻找可用端口并打开浏览器。整个过程不依赖 Node、Python 或外部网络。
/// </summary>
internal static class DemoLauncher
{
    private const int FirstPort = 18080;
    private const int LastPort = 18089;

    private static string _webRoot = string.Empty;

    private static void Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;
        Console.Title = "迅雷 AI 片库 Demo";

        _webRoot = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "www"));
        string indexPath = Path.Combine(_webRoot, "index.html");
        if (!File.Exists(indexPath))
        {
            Console.WriteLine("启动失败：没有找到 www\\index.html。请完整解压提交包后再运行。");
            WaitBeforeExit();
            return;
        }

        TcpListener listener = StartOnAvailablePort();
        if (listener == null)
        {
            Console.WriteLine("启动失败：端口 18080-18089 均被占用。请关闭占用端口的程序后重试。");
            WaitBeforeExit();
            return;
        }

        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        string url = "http://127.0.0.1:" + port + "/";

        Console.WriteLine("迅雷 AI 片库 Demo 已启动");
        Console.WriteLine("访问地址：" + url);
        Console.WriteLine("请保留此窗口；关闭窗口即可停止 Demo。");

        // --no-open 仅用于自动化验收，评委正常双击时仍会自动打开浏览器。
        bool shouldOpenBrowser = args.Length == 0 || !string.Equals(
            args[0],
            "--no-open",
            StringComparison.OrdinalIgnoreCase);
        try
        {
            if (shouldOpenBrowser)
            {
                Process.Start(url);
            }
        }
        catch
        {
            Console.WriteLine("浏览器未能自动打开，请手动访问上方地址。");
        }

        // 每个请求放入线程池处理，避免视频加载阻塞页面资源。
        while (true)
        {
            TcpClient client = listener.AcceptTcpClient();
            ThreadPool.QueueUserWorkItem(HandleClient, client);
        }
    }

    /// <summary>
    /// 仅监听 127.0.0.1，防止局域网中的其他设备访问本地演示服务。
    /// </summary>
    private static TcpListener StartOnAvailablePort()
    {
        for (int port = FirstPort; port <= LastPort; port++)
        {
            try
            {
                TcpListener listener = new TcpListener(IPAddress.Loopback, port);
                listener.Start();
                return listener;
            }
            catch (SocketException)
            {
                // 当前端口被占用时继续尝试下一个端口。
            }
        }

        return null;
    }

    private static void HandleClient(object state)
    {
        using (TcpClient client = (TcpClient)state)
        using (NetworkStream stream = client.GetStream())
        {
            try
            {
                client.ReceiveTimeout = 10000;
                client.SendTimeout = 30000;
                ServeRequest(stream);
            }
            catch (Exception)
            {
                // 浏览器取消图片或视频请求是正常行为，不需要让启动器退出。
            }
        }
    }

    private static void ServeRequest(NetworkStream stream)
    {
        string requestLine;
        string rangeHeader = null;

        // 浏览器请求头是 ASCII 文本；leaveOpen 保证读取请求头后仍可写入响应。
        using (StreamReader reader = new StreamReader(stream, Encoding.ASCII, false, 4096, true))
        {
            requestLine = reader.ReadLine();
            if (string.IsNullOrWhiteSpace(requestLine))
            {
                return;
            }

            string line;
            while (!string.IsNullOrEmpty(line = reader.ReadLine()))
            {
                if (line.StartsWith("Range:", StringComparison.OrdinalIgnoreCase))
                {
                    rangeHeader = line.Substring(6).Trim();
                }
            }
        }

        string[] requestParts = requestLine.Split(' ');
        if (requestParts.Length < 2)
        {
            WriteTextResponse(stream, "400 Bad Request", "请求格式错误。");
            return;
        }

        string method = requestParts[0].ToUpperInvariant();
        if (method != "GET" && method != "HEAD")
        {
            WriteTextResponse(stream, "405 Method Not Allowed", "仅支持 GET 和 HEAD 请求。");
            return;
        }

        string path = ResolveRequestPath(requestParts[1]);
        if (path == null)
        {
            WriteTextResponse(stream, "403 Forbidden", "拒绝访问该路径。");
            return;
        }

        if (!File.Exists(path))
        {
            WriteTextResponse(stream, "404 Not Found", "文件不存在。");
            return;
        }

        ServeFile(stream, method, path, rangeHeader);
    }

    /// <summary>
    /// 将 URL 映射到 www 目录，并通过完整路径比较阻止 ../ 路径穿越。
    /// </summary>
    private static string ResolveRequestPath(string rawUrl)
    {
        string urlPath = rawUrl.Split('?')[0];
        urlPath = Uri.UnescapeDataString(urlPath).Replace('/', Path.DirectorySeparatorChar);
        urlPath = urlPath.TrimStart(Path.DirectorySeparatorChar);
        if (string.IsNullOrEmpty(urlPath))
        {
            urlPath = "index.html";
        }

        string fullPath = Path.GetFullPath(Path.Combine(_webRoot, urlPath));
        string allowedPrefix = _webRoot.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!fullPath.StartsWith(allowedPrefix, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return fullPath;
    }

    private static void ServeFile(NetworkStream stream, string method, string path, string rangeHeader)
    {
        FileInfo file = new FileInfo(path);
        long start = 0;
        long end = file.Length - 1;
        bool partial = TryParseRange(rangeHeader, file.Length, out start, out end);
        long contentLength = end - start + 1;

        StringBuilder headers = new StringBuilder();
        headers.Append(partial ? "HTTP/1.1 206 Partial Content\r\n" : "HTTP/1.1 200 OK\r\n");
        headers.Append("Content-Type: " + GetContentType(file.Extension) + "\r\n");
        headers.Append("Content-Length: " + contentLength.ToString(CultureInfo.InvariantCulture) + "\r\n");
        headers.Append("Accept-Ranges: bytes\r\n");
        headers.Append("Cache-Control: no-cache\r\n");
        headers.Append("Connection: close\r\n");
        if (partial)
        {
            headers.Append(
                "Content-Range: bytes " +
                start.ToString(CultureInfo.InvariantCulture) + "-" +
                end.ToString(CultureInfo.InvariantCulture) + "/" +
                file.Length.ToString(CultureInfo.InvariantCulture) + "\r\n");
        }
        headers.Append("\r\n");

        byte[] headerBytes = Encoding.ASCII.GetBytes(headers.ToString());
        stream.Write(headerBytes, 0, headerBytes.Length);

        if (method == "HEAD")
        {
            return;
        }

        using (FileStream fileStream = File.OpenRead(path))
        {
            fileStream.Position = start;
            byte[] buffer = new byte[64 * 1024];
            long remaining = contentLength;
            while (remaining > 0)
            {
                int count = fileStream.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                if (count <= 0)
                {
                    break;
                }

                stream.Write(buffer, 0, count);
                remaining -= count;
            }
        }
    }

    /// <summary>
    /// 支持视频播放器常用的单段 bytes 范围请求，使 02:04、11:28 跳转无需下载完整视频。
    /// </summary>
    private static bool TryParseRange(string header, long fileLength, out long start, out long end)
    {
        start = 0;
        end = fileLength - 1;
        if (string.IsNullOrWhiteSpace(header) || !header.StartsWith("bytes=", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        string[] values = header.Substring(6).Split('-');
        long parsedStart;
        long parsedEnd;
        if (values.Length != 2 || !long.TryParse(values[0], out parsedStart))
        {
            return false;
        }

        if (string.IsNullOrEmpty(values[1]))
        {
            parsedEnd = fileLength - 1;
        }
        else if (!long.TryParse(values[1], out parsedEnd))
        {
            return false;
        }

        if (parsedStart < 0 || parsedStart >= fileLength || parsedEnd < parsedStart)
        {
            return false;
        }

        start = parsedStart;
        end = Math.Min(parsedEnd, fileLength - 1);
        return true;
    }

    private static string GetContentType(string extension)
    {
        switch (extension.ToLowerInvariant())
        {
            case ".html": return "text/html; charset=utf-8";
            case ".css": return "text/css; charset=utf-8";
            case ".js": return "application/javascript; charset=utf-8";
            case ".json": return "application/json; charset=utf-8";
            case ".svg": return "image/svg+xml";
            case ".png": return "image/png";
            case ".jpg":
            case ".jpeg": return "image/jpeg";
            case ".mp4": return "video/mp4";
            case ".webm": return "video/webm";
            case ".woff2": return "font/woff2";
            default: return "application/octet-stream";
        }
    }

    private static void WriteTextResponse(NetworkStream stream, string status, string message)
    {
        byte[] body = Encoding.UTF8.GetBytes(message);
        string headers =
            "HTTP/1.1 " + status + "\r\n" +
            "Content-Type: text/plain; charset=utf-8\r\n" +
            "Content-Length: " + body.Length.ToString(CultureInfo.InvariantCulture) + "\r\n" +
            "Connection: close\r\n\r\n";
        byte[] headerBytes = Encoding.ASCII.GetBytes(headers);
        stream.Write(headerBytes, 0, headerBytes.Length);
        stream.Write(body, 0, body.Length);
    }

    private static void WaitBeforeExit()
    {
        Console.WriteLine("按任意键退出。");
        Console.ReadKey();
    }
}
