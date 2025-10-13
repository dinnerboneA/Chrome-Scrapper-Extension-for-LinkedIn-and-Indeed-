<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Symfony\Component\Process\Process;
use Symfony\Component\Process\Exception\ProcessFailedException;

class PageController extends Controller
{
    public function process(Request $request)
    {
        $htmlContent = $request->input('html');
        $url = $request->input('url');

        if (!$htmlContent || !$url) {
            return response()->json(['error' => 'Missing HTML or URL.'], 400);
        }

        $scraperScript = '';
        if (str_contains($url, '/in/')) {
            $scraperScript = 'person_scraper.py';
        } elseif (str_contains($url, '/jobs/view/')) {
            $scraperScript = 'job_scraper.py';
        } elseif (str_contains($url, '/company/')) {
            $scraperScript = 'company_scraper.py';
        } elseif (str_contains($url, 'indeed.com/cmp/')) {
            $scraperScript = 'indeed_company_scraper.py';
        } elseif (str_contains($url, 'indeed.') && str_contains($url, 'viewjob')) {
            $scraperScript = 'indeed_job_scraper.py';                             
            $tempFileName = 'temp_page_' . time() . '.html';                       
            Storage::put('scraped_pages/' . $tempFileName, $htmlContent);          
            $argument = Storage::path('scraped_pages/' . $tempFileName);           
        } else {
            return response()->json(['error' => 'This page type is not supported.'], 400);
        }
        
        $newFileName = 'temp_page_' . time() . '.html';
        Storage::put('scraped_pages/' . $newFileName, $htmlContent);
        
        try {
            $htmlFilePath = Storage::path('scraped_pages/' . $newFileName);
            $process = new Process([base_path('venv/Scripts/python.exe'), base_path('scripts/' . $scraperScript), $htmlFilePath]);
            $process->run();

            if (!$process->isSuccessful()) {
                throw new ProcessFailedException($process);
            }

            $pythonOutput = $process->getOutput();
            $cleanedOutput = preg_replace('/^[\x00-\x1F\x80-\xFF]/', '', trim($pythonOutput));
            $data = json_decode($cleanedOutput, true);

            if (json_last_error() !== JSON_ERROR_NONE) {
                Log::error("JSON Decode Error: " . json_last_error_msg());
                throw new \Exception("Failed to decode JSON from Python script.");
            }
        } catch (\Exception $exception) {
            Log::error('A script error occurred: ' . $exception->getMessage());
            return response()->json(['error' => 'The server script failed.'], 500);
        } finally {
            if (isset($newFileName)) {
                Storage::delete('scraped_pages/' . $newFileName);
            }
        }

        return response()->json($data);
    }
}