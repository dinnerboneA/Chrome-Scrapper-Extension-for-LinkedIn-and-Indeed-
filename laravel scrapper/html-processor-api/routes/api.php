<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\PageController;

Route::post('/process-page', [PageController::class, 'process']);