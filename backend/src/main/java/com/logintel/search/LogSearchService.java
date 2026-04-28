package com.logintel.search;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.SortOrder;
import co.elastic.clients.elasticsearch._types.query_dsl.BoolQuery;
import co.elastic.clients.elasticsearch._types.query_dsl.Query;
import co.elastic.clients.elasticsearch.core.SearchRequest;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.elasticsearch.core.search.Hit;
import com.logintel.auth.RoleAccess;
import com.logintel.model.LogEntry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;


import java.io.IOException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Handles all Elasticsearch query logic with RBAC enforcement.
 * Supports filtering by: level, service, time range, keyword, and user role.
 *
 * RBAC is enforced at this layer — every query is scoped to the service
 * prefixes the user's role allows. This prevents bypass via direct API calls.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LogSearchService {

    private static final String INDEX_NAME = "logs";
    private static final int MAX_RESULTS = 200;

    private final ElasticsearchClient elasticsearchClient;

    /**
     * Main search method — builds a boolean query from filters + RBAC.
     *
     * @param level           e.g. "ERROR", "WARN", "INFO" — null means all levels
     * @param service         e.g. "payment-service" — null means all services (exact match)
     * @param servicePatterns list of service name prefixes (e.g. ["docker-", "nginx"]) — OR logic
     * @param keyword         full-text search in message field — null means no filter
     * @param hoursAgo        e.g. 1, 6, 24 — how far back to search
     * @param role            user's RBAC role — restricts which services are queryable
     * @return list of matching LogEntry objects sorted by time (newest first)
     */
    public List<LogEntry> searchLogs(
            String level,
            String service,
            List<String> servicePatterns,
            String keyword,
            double hoursAgo,
            String role
    ) throws IOException {

        // Calculate time range — convert hours to minutes for sub-hour precision
        long minutes = Math.max(1, Math.round(hoursAgo * 60));
        Instant from = Instant.now().minus(minutes, ChronoUnit.MINUTES);

        // Build a list of filter conditions (all must match = AND logic)
        List<Query> filters = new ArrayList<>();

        // Always filter by time range
        filters.add(Query.of(q -> q
                .range(r -> r
                        .field("timestamp")
                        .gte(co.elastic.clients.json.JsonData.of(from.toString()))
                )
        ));

        // Add level filter only if provided
        if (level != null && !level.isBlank()) {
            filters.add(Query.of(q -> q
                    .term(t -> t
                            .field("level.keyword")   // .keyword = exact match
                            .value(level.toUpperCase())
                    )
            ));
        }

        // ── RBAC enforcement ────────────────────────────────────────
        // Get the service prefixes this role is allowed to access
        List<String> allowedPrefixes = RoleAccess.getAllowedServicePrefixes(role);

        // Add service filter — exact match takes priority over patterns
        if (service != null && !service.isBlank()) {
            // Verify the requested service falls within the role's allowed prefixes
            if (!allowedPrefixes.isEmpty()) {
                boolean allowed = allowedPrefixes.stream()
                        .anyMatch(prefix -> service.startsWith(prefix) || service.equals(prefix));
                if (!allowed) {
                    log.warn("RBAC denied: role={} tried to access service={}", role, service);
                    return List.of(); // Access denied — return empty
                }
            }
            filters.add(Query.of(q -> q
                    .term(t -> t
                            .field("service.keyword")
                            .value(service)
                    )
            ));
        } else if (servicePatterns != null && !servicePatterns.isEmpty()) {
            // Intersect requested patterns with allowed patterns
            List<String> effectivePatterns = servicePatterns;
            if (!allowedPrefixes.isEmpty()) {
                effectivePatterns = servicePatterns.stream()
                        .filter(pattern -> allowedPrefixes.stream()
                                .anyMatch(allowed -> pattern.startsWith(allowed) || allowed.startsWith(pattern)))
                        .toList();
                if (effectivePatterns.isEmpty()) {
                    log.warn("RBAC denied: role={} has no overlap with servicePatterns={}", role, servicePatterns);
                    return List.of();
                }
            }

            List<Query> prefixQueries = new ArrayList<>();
            for (String pattern : effectivePatterns) {
                String trimmed = pattern.trim();
                if (!trimmed.isEmpty()) {
                    prefixQueries.add(Query.of(q -> q
                            .prefix(p -> p
                                    .field("service.keyword")
                                    .value(trimmed)
                            )
                    ));
                }
            }
            if (!prefixQueries.isEmpty()) {
                filters.add(Query.of(q -> q
                        .bool(b -> b.should(prefixQueries).minimumShouldMatch("1"))
                ));
            }
        } else if (!allowedPrefixes.isEmpty()) {
            // No service/patterns specified but user is NOT admin —
            // restrict to only their allowed service prefixes
            List<Query> rbacQueries = new ArrayList<>();
            for (String prefix : allowedPrefixes) {
                rbacQueries.add(Query.of(q -> q
                        .prefix(p -> p
                                .field("service.keyword")
                                .value(prefix)
                        )
                ));
            }
            filters.add(Query.of(q -> q
                    .bool(b -> b.should(rbacQueries).minimumShouldMatch("1"))
            ));
        }
        // If allowedPrefixes is empty (ADMIN), no service restriction is applied

        // Add full-text keyword search only if provided
        if (keyword != null && !keyword.isBlank()) {
            filters.add(Query.of(q -> q
                    .match(m -> m
                            .field("message")
                            .query(keyword)
                    )
            ));
        }

        // Combine all filters into a bool query
        BoolQuery boolQuery = BoolQuery.of(b -> b.filter(filters));

        // Build the full search request
        SearchRequest searchRequest = SearchRequest.of(s -> s
                .index(INDEX_NAME)
                .query(q -> q.bool(boolQuery))
                .sort(sort -> sort
                        .field(f -> f
                                .field("timestamp")
                                .order(SortOrder.Desc)  // newest logs first
                        )
                )
                .size(MAX_RESULTS)
        );

        // Execute and map results
        SearchResponse<LogEntry> response =
                elasticsearchClient.search(searchRequest, LogEntry.class);

        List<LogEntry> results = response.hits().hits()
                .stream()
                .map(Hit::source)
                .toList();

        log.info("Search returned {} logs for role={}, level={}, service={}, servicePatterns={}, hoursAgo={}",
                results.size(), role, level, service, servicePatterns, hoursAgo);

        return results;
    }

    /**
     * Returns all distinct service names from the logs index,
     * filtered by the user's RBAC role.
     */
    public List<String> getDistinctServices(String role) throws IOException {
        List<String> allServices = getDistinctServicesUnfiltered();

        List<String> allowedPrefixes = RoleAccess.getAllowedServicePrefixes(role);
        if (allowedPrefixes.isEmpty()) {
            return allServices; // ADMIN sees everything
        }

        return allServices.stream()
                .filter(svc -> allowedPrefixes.stream()
                        .anyMatch(prefix -> svc.startsWith(prefix) || svc.equals(prefix)))
                .toList();
    }

    private List<String> getDistinctServicesUnfiltered() throws IOException {
        SearchResponse<Void> response = elasticsearchClient.search(s -> s
                .index(INDEX_NAME)
                .size(0)
                .aggregations("unique_services", a -> a
                        .terms(t -> t
                                .field("service.keyword")
                                .size(100)
                        )
                ),
                Void.class
        );

        List<String> services = new ArrayList<>();
        var buckets = response.aggregations()
                .get("unique_services")
                .sterms()
                .buckets()
                .array();

        for (var bucket : buckets) {
            services.add(bucket.key().stringValue());
        }

        log.info("Found {} distinct services", services.size());
        return services;
    }

    /**
     * Returns log counts per service for the given time range,
     * filtered by the user's RBAC role.
     */
    public List<Map<String, Object>> getServiceStats(double hoursAgo, String role) throws IOException {
        long minutes = Math.max(1, Math.round(hoursAgo * 60));
        Instant from = Instant.now().minus(minutes, ChronoUnit.MINUTES);

        // Build query with time filter + optional RBAC prefix filter
        List<String> allowedPrefixes = RoleAccess.getAllowedServicePrefixes(role);

        SearchResponse<Void> response;

        if (allowedPrefixes.isEmpty()) {
            // ADMIN — no service restriction
            response = elasticsearchClient.search(s -> s
                    .index(INDEX_NAME)
                    .size(0)
                    .query(q -> q
                            .range(r -> r
                                    .field("timestamp")
                                    .gte(co.elastic.clients.json.JsonData.of(from.toString()))
                            )
                    )
                    .aggregations("service_counts", a -> a
                            .terms(t -> t
                                    .field("service.keyword")
                                    .size(100)
                            )
                    ),
                    Void.class
            );
        } else {
            // Non-admin — add RBAC prefix filter
            List<Query> rbacQueries = new ArrayList<>();
            for (String prefix : allowedPrefixes) {
                rbacQueries.add(Query.of(q -> q
                        .prefix(p -> p
                                .field("service.keyword")
                                .value(prefix)
                        )
                ));
            }

            response = elasticsearchClient.search(s -> s
                    .index(INDEX_NAME)
                    .size(0)
                    .query(q -> q
                            .bool(b -> b
                                    .filter(f -> f
                                            .range(r -> r
                                                    .field("timestamp")
                                                    .gte(co.elastic.clients.json.JsonData.of(from.toString()))
                                            )
                                    )
                                    .filter(f -> f
                                            .bool(rb -> rb
                                                    .should(rbacQueries)
                                                    .minimumShouldMatch("1")
                                            )
                                    )
                            )
                    )
                    .aggregations("service_counts", a -> a
                            .terms(t -> t
                                    .field("service.keyword")
                                    .size(100)
                            )
                    ),
                    Void.class
            );
        }

        List<Map<String, Object>> stats = new ArrayList<>();
        var buckets = response.aggregations()
                .get("service_counts")
                .sterms()
                .buckets()
                .array();

        for (var bucket : buckets) {
            Map<String, Object> entry = new HashMap<>();
            entry.put("service", bucket.key().stringValue());
            entry.put("count", bucket.docCount());
            stats.add(entry);
        }

        log.info("Service stats: {} services in last {} hours (role={})", stats.size(), hoursAgo, role);
        return stats;
    }
}
