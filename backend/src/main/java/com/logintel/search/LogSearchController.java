package com.logintel.search;

import com.logintel.auth.RoleAccess;
import com.logintel.model.LogEntry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * REST API controller — exposes log search endpoints with RBAC.
 *
 * All endpoints (except /health) require a valid JWT token.
 * The user's role is extracted from the security context and passed
 * to the service layer to enforce data-level access control.
 *
 * The Python AI service forwards the user's JWT when calling these
 * endpoints, ensuring role-based filtering is applied end-to-end.
 *
 * Base URL: http://localhost:8080/api/logs
 */
@Slf4j
@RestController
@RequestMapping("/api/logs")
@RequiredArgsConstructor
public class LogSearchController {

    private final LogSearchService logSearchService;

    /**
     * Extracts the role from the Spring Security context.
     * The JwtAuthFilter stores the role as authentication details.
     * Returns BASIC_USER if no role is found (shouldn't happen if auth is required).
     */
    private String extractRole() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getDetails() instanceof String role) {
            return role;
        }
        return RoleAccess.ROLE_BASIC_USER;
    }

    /**
     * Search logs with optional filters + RBAC enforcement.
     *
     * Example calls:
     *   GET /api/logs/search?level=ERROR&hoursAgo=6
     *   GET /api/logs/search?service=payment-service&hoursAgo=24
     *   GET /api/logs/search?keyword=timeout&level=ERROR&hoursAgo=1
     *   GET /api/logs/search?servicePatterns=docker-,nginx&hoursAgo=6
     *
     * The role is automatically extracted from the JWT and applied as a filter.
     */
    @GetMapping("/search")
    public ResponseEntity<?> searchLogs(
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String service,
            @RequestParam(required = false) String servicePatterns,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "24") double hoursAgo
    ) {
        String role = extractRole();
        log.info("Search request → role={}, level={}, service={}, servicePatterns={}, keyword={}, hoursAgo={}",
                role, level, service, servicePatterns, keyword, hoursAgo);

        try {
            // Parse servicePatterns into a list if provided
            List<String> patterns = null;
            if (servicePatterns != null && !servicePatterns.isBlank()) {
                patterns = List.of(servicePatterns.split(","));
            }

            List<LogEntry> logs = logSearchService.searchLogs(level, service, patterns, keyword, hoursAgo, role);

            // Return both the logs and metadata
            return ResponseEntity.ok(Map.of(
                    "logs", logs,
                    "count", logs.size(),
                    "filters", Map.of(
                            "level", level != null ? level : "all",
                            "service", service != null ? service : (servicePatterns != null ? servicePatterns : "all"),
                            "keyword", keyword != null ? keyword : "",
                            "hoursAgo", hoursAgo
                    )
            ));

        } catch (IOException e) {
            log.error("Elasticsearch query failed: {}", e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of(
                    "error", "Search failed",
                    "message", e.getMessage()
            ));
        }
    }

    /**
     * Returns log counts per service for the dashboard chart, filtered by role.
     * GET /api/logs/stats?hoursAgo=24
     */
    @GetMapping("/stats")
    public ResponseEntity<?> getStats(
            @RequestParam(defaultValue = "24") double hoursAgo
    ) {
        String role = extractRole();
        try {
            var stats = logSearchService.getServiceStats(hoursAgo, role);
            return ResponseEntity.ok(Map.of("stats", stats));
        } catch (IOException e) {
            log.error("Failed to fetch stats: {}", e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of(
                    "error", "Failed to fetch stats",
                    "message", e.getMessage()
            ));
        }
    }

    /**
     * Returns all distinct service names from the logs index, filtered by role.
     * GET /api/logs/services
     */
    @GetMapping("/services")
    public ResponseEntity<?> getServices() {
        String role = extractRole();
        try {
            List<String> services = logSearchService.getDistinctServices(role);
            return ResponseEntity.ok(Map.of("services", services));
        } catch (IOException e) {
            log.error("Failed to fetch services: {}", e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of(
                    "error", "Failed to fetch services",
                    "message", e.getMessage()
            ));
        }
    }

    /**
     * Health check endpoint — remains public (no auth required).
     * GET /api/logs/health
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "log-intelligence-backend"));
    }
}
