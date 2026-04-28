package com.logintel.auth;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Defines RBAC role-to-log-source mappings.
 *
 * Each role has access to specific log source categories.
 * Source categories map to Elasticsearch service name prefixes
 * (same prefixes used in the AI service's SOURCE_SERVICE_MAP).
 *
 * ADMIN          → all log types
 * DEVOPS         → system, docker, github (CI/CD), webserver
 * BACKEND_DEV    → file, database
 * DATA_ANALYST   → database
 * SECURITY_ENG   → system, webserver
 * BASIC_USER     → file only
 */
public final class RoleAccess {

    private RoleAccess() {}

    public static final String ROLE_ADMIN = "ADMIN";
    public static final String ROLE_DEVOPS = "DEVOPS";
    public static final String ROLE_BACKEND_DEVELOPER = "BACKEND_DEVELOPER";
    public static final String ROLE_DATA_ANALYST = "DATA_ANALYST";
    public static final String ROLE_SECURITY_ENGINEER = "SECURITY_ENGINEER";
    public static final String ROLE_BASIC_USER = "BASIC_USER";

    public static final Set<String> ALL_ROLES = Set.of(
            ROLE_ADMIN, ROLE_DEVOPS, ROLE_BACKEND_DEVELOPER,
            ROLE_DATA_ANALYST, ROLE_SECURITY_ENGINEER, ROLE_BASIC_USER
    );

    /** Source category → Elasticsearch service name prefixes */
    public static final Map<String, List<String>> SOURCE_SERVICE_PREFIXES = Map.of(
            "system",    List.of("windows-event"),
            "file",      List.of("test-app", "file-"),
            "database",  List.of("mariadb", "mysql", "postgresql"),
            "docker",    List.of("docker"),
            "github",    List.of("github-actions"),
            "webserver", List.of("nginx", "apache")
    );

    /** Role → allowed source categories */
    private static final Map<String, List<String>> ROLE_SOURCES = Map.of(
            ROLE_ADMIN,              List.of("system", "file", "database", "docker", "github", "webserver"),
            ROLE_DEVOPS,             List.of("system", "docker", "github", "webserver"),
            ROLE_BACKEND_DEVELOPER,  List.of("file", "database"),
            ROLE_DATA_ANALYST,       List.of("database"),
            ROLE_SECURITY_ENGINEER,  List.of("system", "webserver"),
            ROLE_BASIC_USER,         List.of("file")
    );

    /**
     * Returns the source categories a role can access.
     * e.g. DEVOPS → ["system", "docker", "github", "webserver"]
     */
    public static List<String> getAllowedSources(String role) {
        return ROLE_SOURCES.getOrDefault(role, List.of());
    }

    /**
     * Returns all Elasticsearch service name prefixes the role can query.
     * Flattens source categories → service prefixes.
     * e.g. DEVOPS → ["windows-event", "docker", "github-actions", "nginx", "apache"]
     */
    public static List<String> getAllowedServicePrefixes(String role) {
        if (ROLE_ADMIN.equals(role)) {
            return List.of(); // empty = no restriction
        }
        return getAllowedSources(role).stream()
                .flatMap(source -> SOURCE_SERVICE_PREFIXES.getOrDefault(source, List.of()).stream())
                .toList();
    }

    /**
     * Checks if a role can access a specific source category.
     */
    public static boolean canAccessSource(String role, String source) {
        if (ROLE_ADMIN.equals(role)) return true;
        return getAllowedSources(role).contains(source);
    }

    /**
     * Validates if a string is a known role.
     */
    public static boolean isValidRole(String role) {
        return role != null && ALL_ROLES.contains(role);
    }
}
