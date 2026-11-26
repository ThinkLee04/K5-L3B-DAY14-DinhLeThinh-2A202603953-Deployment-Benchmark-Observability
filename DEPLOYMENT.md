# Triển khai agent Part 6

**Nền tảng:** Render  
**URL public:** [day14-agent-ubeq.onrender.com](https://day14-agent-ubeq.onrender.com)

## Cấu hình Render

Blueprint triển khai web service `day14-agent` (Docker) và Key Value `day14-redis` ở Singapore. [render.yaml](06-lab-complete/render.yaml)

| Biến | Nguồn giá trị |
| --- | --- |
| `PORT` | Render cấp. Dockerfile truyền giá trị này cho Uvicorn. |
| `REDIS_URL` | Blueprint lấy `connectionString` của `day14-redis`. |
| `AGENT_API_KEY` | Render sinh bằng `generateValue: true`. |
| `ENVIRONMENT` | Blueprint đặt `production`. |
| `LOG_LEVEL` | App mặc định `INFO`. |
| `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` | App mặc định 10 request/phút và 1 USD/ngày UTC. |

## Kiểm tra trên URL public

Dán khối sau vào PowerShell. Nhập `AGENT_API_KEY` từ mục Environment của web service khi được hỏi. Terminal ẩn giá trị khi nhập.

```powershell
$day14Base = 'https://day14-agent-ubeq.onrender.com'

function Show-Day14Status {
    param([string]$Label, [string]$Path, [hashtable]$RequestOptions = @{})

    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 90 -Uri "$day14Base$Path" @RequestOptions
        "$Label -> $([int]$response.StatusCode)"
    } catch {
        if ($null -eq $_.Exception.Response) { throw }
        "$Label -> $([int]$_.Exception.Response.StatusCode)"
    }
}

$day14Post = @{
    Method = 'Post'
    ContentType = 'application/json'
    Body = '{"question":"Hello"}'
}

Show-Day14Status 'GET /health' '/health'
Show-Day14Status 'GET /ready' '/ready'
Show-Day14Status 'POST /ask thiếu key' '/ask' $day14Post

$day14Key = Read-Host 'AGENT_API_KEY trên Render' -AsSecureString
try {
    $day14Post.Headers = @{ 'X-API-Key' = [System.Net.NetworkCredential]::new('', $day14Key).Password }
    Show-Day14Status 'POST /ask có key' '/ask' $day14Post
} finally {
    $day14Post.Remove('Headers')
    Remove-Variable day14Key
}
```

| Request | HTTP thực tế |
| --- | ---: |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` thiếu key | 401 |
| `POST /ask` có key | 200 |

## Bằng chứng cần nộp

| Ảnh | Nội dung |
| --- | --- |
| [Dashboard Render](screenshots/dashboard.png) | `day14-agent` ở trạng thái Deployed, `day14-redis` ở trạng thái Available. |
| [Web service đang chạy](screenshots/running.png) | URL public và commit `87d5370` trên nhánh `main` ở trạng thái Live tại thời điểm chụp. |
| [Kết quả bốn request](screenshots/test.png) | PowerShell hiển thị 200, 200, 401, 200. API key được ẩn khi nhập. |
