package com.logintel.auth;

import org.springframework.stereotype.Component;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Simple in-memory rate limiter for auth endpoints.
 *
 * Tracks failed login attempts per IP address.
 * After 5 failed attempts within the window, the IP is blocked
 * for 15 minutes to prevent brute force attacks.
 *
 * Successful logins reset the counter for that IP.
 */
@Component
public class RateLimiter {

    private static final int MAX_ATTEMPTS = 5;
    private static final long BLOCK_DURATION_MS = 15 * 60 * 1000; // 15 minutes

    private final ConcurrentHashMap<String, AttemptInfo> attempts = new ConcurrentHashMap<>();

    /**
     * Check if an IP is currently blocked.
     */
    public boolean isBlocked(String ip) {
        AttemptInfo info = attempts.get(ip);
        if (info == null) return false;

        // If block has expired, clear it
        if (info.blockedUntil > 0 && System.currentTimeMillis() > info.blockedUntil) {
            attempts.remove(ip);
            return false;
        }

        return info.blockedUntil > 0;
    }

    /**
     * Record a failed attempt. Returns true if the IP is now blocked.
     */
    public boolean recordFailure(String ip) {
        AttemptInfo info = attempts.computeIfAbsent(ip, k -> new AttemptInfo());
        int count = info.failCount.incrementAndGet();

        if (count >= MAX_ATTEMPTS) {
            info.blockedUntil = System.currentTimeMillis() + BLOCK_DURATION_MS;
            return true;
        }
        return false;
    }

    /**
     * Reset attempts on successful login.
     */
    public void recordSuccess(String ip) {
        attempts.remove(ip);
    }

    /**
     * Returns remaining attempts before block.
     */
    public int remainingAttempts(String ip) {
        AttemptInfo info = attempts.get(ip);
        if (info == null) return MAX_ATTEMPTS;
        return Math.max(0, MAX_ATTEMPTS - info.failCount.get());
    }

    private static class AttemptInfo {
        final AtomicInteger failCount = new AtomicInteger(0);
        volatile long blockedUntil = 0;
    }
}
