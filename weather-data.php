<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');

if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    http_response_code(405);
    header('Allow: GET');
    echo json_encode(['error' => 'Only GET requests are supported.']);
    exit;
}

$weatherUrl = 'https://www.weatherlink.com/embeddablePage/summaryData/3f51dabcd7194bfeb01298ee07821187';
$response = false;
$upstreamStatus = 0;

if (function_exists('curl_init')) {
    $curl = curl_init($weatherUrl);
    curl_setopt_array($curl, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT => 12,
        CURLOPT_HTTPHEADER => ['Accept: application/json'],
        CURLOPT_USERAGENT => 'ApaseoWeatherCard/1.0',
    ]);
    $curlResponse = curl_exec($curl);
    $upstreamStatus = (int)curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
    curl_close($curl);

    if (is_string($curlResponse)) {
        $response = $curlResponse;
    }
} elseif (extension_loaded('openssl') && in_array('https', stream_get_wrappers(), true)) {
    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'timeout' => 12,
            'ignore_errors' => true,
            'header' => "Accept: application/json\r\nUser-Agent: ApaseoWeatherCard/1.0\r\n",
        ],
    ]);

    $streamResponse = @file_get_contents($weatherUrl, false, $context);
    $statusLine = $http_response_header[0] ?? '';
    if (preg_match('/\s(\d{3})\s/', $statusLine, $matches)) {
        $upstreamStatus = (int)$matches[1];
    }
    if (is_string($streamResponse)) {
        $response = $streamResponse;
    }
} else {
    http_response_code(500);
    echo json_encode(['error' => 'PHP hosting must enable cURL or OpenSSL for HTTPS requests.']);
    exit;
}

if ($response === false) {
    http_response_code(502);
    echo json_encode(['error' => 'Could not retrieve data from WeatherLink.']);
    exit;
}

if ($upstreamStatus !== 200) {
    http_response_code(502);
    echo json_encode(['error' => 'WeatherLink returned an unsuccessful response.']);
    exit;
}

try {
    $data = json_decode($response, true, 512, JSON_THROW_ON_ERROR);
} catch (JsonException $error) {
    http_response_code(502);
    echo json_encode(['error' => 'WeatherLink returned invalid JSON.']);
    exit;
}

if (!is_array($data) || !isset($data['currConditionValues']) || !is_array($data['currConditionValues'])) {
    http_response_code(502);
    echo json_encode(['error' => 'WeatherLink response is missing station readings.']);
    exit;
}

echo json_encode($data, JSON_THROW_ON_ERROR);
