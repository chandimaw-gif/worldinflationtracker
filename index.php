<?php
$target = 'http://127.0.0.1:8000';
$uri = $_SERVER['REQUEST_URI'];
$url = $target . $uri;

$ch = curl_init($url);
$method = $_SERVER['REQUEST_METHOD'];
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);

$headers = [];
$skip = ['Host', 'Connection', 'Accept-Encoding', 'Content-Length'];

if (function_exists('getallheaders')) {
    $requestHeaders = getallheaders();
} else {
    $requestHeaders = [];
    foreach ($_SERVER as $key => $value) {
        if (strpos($key, 'HTTP_') === 0) {
            $headerName = str_replace('_', '-', substr($key, 5));
            $requestHeaders[$headerName] = $value;
        }
    }
}

foreach ($requestHeaders as $key => $value) {
    if (!in_array($key, $skip)) {
        $headers[] = "$key: $value";
    }
}
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

if (!in_array($method, ['GET', 'HEAD', 'OPTIONS'])) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, file_get_contents('php://input'));
}

curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HEADER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false);

$response = curl_exec($ch);

if ($response === false) {
    http_response_code(502);
    echo "Bad Gateway: Could not connect to Django app on port 8000";
    curl_close($ch);
    exit;
}

$headerSize = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
$statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$responseHeaders = substr($response, 0, $headerSize);
$responseBody = substr($response, $headerSize);

foreach (explode("\r\n", $responseHeaders) as $line) {
    if (stripos($line, 'HTTP/') === 0) {
        http_response_code($statusCode);
    } elseif (stripos($line, 'Transfer-Encoding:') === false && 
              stripos($line, 'Connection:') === false &&
              strlen($line) > 0) {
        header($line);
    }
}

echo $responseBody;
curl_close($ch);
