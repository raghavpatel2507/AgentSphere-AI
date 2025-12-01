#!/usr/bin/env node

/**
 * Wrapper script for @isaacphi/mcp-gdrive that filters out non-JSON stdout messages
 * This prevents JSONRPC parsing errors in the MCP client
 */

const { spawn } = require('child_process');

// Spawn the actual mcp-gdrive process
const child = spawn('npx', ['-y', '@isaacphi/mcp-gdrive'], {
    stdio: ['inherit', 'pipe', 'inherit'],
    env: process.env
});

let jsonStarted = false;

// Filter stdout to only pass through JSON messages
child.stdout.on('data', (data) => {
    const lines = data.toString().split('\n');

    for (const line of lines) {
        if (!line.trim()) continue;

        // Check if the line looks like JSON (starts with { or [)
        const trimmed = line.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
            jsonStarted = true;
            process.stdout.write(line + '\n');
        } else if (jsonStarted) {
            // Once JSON has started, pass everything through
            process.stdout.write(line + '\n');
        } else {
            // Non-JSON messages before JSON starts - redirect to stderr
            process.stderr.write(`[gdrive-debug] ${line}\n`);
        }
    }
});

child.on('error', (error) => {
    process.stderr.write(`Error spawning mcp-gdrive: ${error.message}\n`);
    process.exit(1);
});

child.on('exit', (code) => {
    process.exit(code || 0);
});

// Handle process signals
process.on('SIGTERM', () => child.kill('SIGTERM'));
process.on('SIGINT', () => child.kill('SIGINT'));
