package com.logintel.auth;

import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Authentication REST controller.
 *
 * POST /api/auth/register — create a new account with role (stored in MongoDB)
 * POST /api/auth/login    — authenticate and receive JWT with role claim
 * GET  /api/auth/me       — validate token and return user info + role
 * GET  /api/auth/roles    — list all available roles
 *
 * Security:
 * - Passwords hashed with BCrypt
 * - Rate limiting: 5 failed attempts → IP blocked for 15 minutes
 * - Password must be at least 8 characters with uppercase, lowercase, number
 * - JWT includes role claim for RBAC enforcement
 */
@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final JwtUtil jwtUtil;
    private final PasswordEncoder passwordEncoder;
    private final UserRepository userRepository;
    private final RateLimiter rateLimiter;

    /**
     * Register a new user with a role.
     * Request body: { "email": "...", "password": "...", "name": "...", "role": "..." }
     * If no role specified, defaults to BASIC_USER.
     */
    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String ip = getClientIp(request);

        if (rateLimiter.isBlocked(ip)) {
            return ResponseEntity.status(429).body(Map.of(
                    "error", "Too many attempts. Please try again in 15 minutes."
            ));
        }

        String email = body.get("email");
        String password = body.get("password");
        String name = body.getOrDefault("name", "");
        String role = body.getOrDefault("role", RoleAccess.ROLE_BASIC_USER);

        if (email == null || password == null || email.isBlank() || password.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Email and password are required"));
        }

        // Validate role
        if (!RoleAccess.isValidRole(role)) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Invalid role. Valid roles: " + String.join(", ", RoleAccess.ALL_ROLES)
            ));
        }

        // Password strength validation
        String passwordError = validatePassword(password);
        if (passwordError != null) {
            return ResponseEntity.badRequest().body(Map.of("error", passwordError));
        }

        if (userRepository.existsByEmail(email)) {
            return ResponseEntity.badRequest().body(Map.of("error", "Account already exists. Please log in."));
        }

        // Hash password with BCrypt before storing
        String hashedPassword = passwordEncoder.encode(password);
        User user = new User(email, hashedPassword, name, role);
        userRepository.save(user);

        // Generate JWT token with role
        String token = jwtUtil.generateToken(email, role);

        log.info("User registered: {} with role {}", email, role);
        return ResponseEntity.ok(Map.of(
                "token", token,
                "email", email,
                "name", name,
                "role", role,
                "allowedSources", RoleAccess.getAllowedSources(role),
                "message", "Account created successfully"
        ));
    }

    /**
     * Login with existing credentials.
     * Request body: { "email": "...", "password": "..." }
     */
    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody Map<String, String> body, HttpServletRequest request) {
        String ip = getClientIp(request);

        // Check if IP is blocked due to too many failed attempts
        if (rateLimiter.isBlocked(ip)) {
            return ResponseEntity.status(429).body(Map.of(
                    "error", "Too many failed attempts. Please try again in 15 minutes."
            ));
        }

        String email = body.get("email");
        String password = body.get("password");

        if (email == null || password == null || email.isBlank() || password.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Email and password are required"));
        }

        var userOpt = userRepository.findByEmail(email);
        if (userOpt.isEmpty() || !passwordEncoder.matches(password, userOpt.get().getPassword())) {
            // Record failed attempt
            boolean blocked = rateLimiter.recordFailure(ip);
            int remaining = rateLimiter.remainingAttempts(ip);

            log.warn("Failed login attempt for {} from IP {} ({} attempts remaining)",
                    email, ip, remaining);

            String error = blocked
                    ? "Too many failed attempts. Account locked for 15 minutes."
                    : "Invalid email or password. " + remaining + " attempt(s) remaining.";

            return ResponseEntity.status(401).body(Map.of("error", error));
        }

        // Successful login — reset rate limiter
        rateLimiter.recordSuccess(ip);

        User user = userOpt.get();
        String role = user.getRole() != null ? user.getRole() : RoleAccess.ROLE_BASIC_USER;
        String token = jwtUtil.generateToken(email, role);

        log.info("User logged in: {} (role: {})", email, role);
        return ResponseEntity.ok(Map.of(
                "token", token,
                "email", email,
                "name", user.getName(),
                "role", role,
                "allowedSources", RoleAccess.getAllowedSources(role),
                "message", "Login successful"
        ));
    }

    /**
     * Validate the current token and return user info + role + allowed sources.
     * GET /api/auth/me — requires valid JWT in Authorization header
     */
    @GetMapping("/me")
    public ResponseEntity<?> me(@RequestHeader(value = "Authorization", required = false) String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return ResponseEntity.status(401).body(Map.of("error", "Not authenticated"));
        }

        String token = authHeader.substring(7);
        if (!jwtUtil.isValid(token)) {
            return ResponseEntity.status(401).body(Map.of("error", "Invalid or expired token"));
        }

        String email = jwtUtil.extractEmail(token);
        String role = jwtUtil.extractRole(token);

        var userOpt = userRepository.findByEmail(email);
        if (userOpt.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of("error", "User not found"));
        }

        User user = userOpt.get();
        // Use the role from the DB (not token) to catch role updates
        String currentRole = user.getRole() != null ? user.getRole() : RoleAccess.ROLE_BASIC_USER;

        return ResponseEntity.ok(Map.of(
                "email", email,
                "name", user.getName(),
                "role", currentRole,
                "allowedSources", RoleAccess.getAllowedSources(currentRole)
        ));
    }

    /**
     * Returns all available roles and their allowed source categories.
     * GET /api/auth/roles
     */
    @GetMapping("/roles")
    public ResponseEntity<?> getRoles() {
        var rolesInfo = RoleAccess.ALL_ROLES.stream()
                .sorted()
                .map(role -> Map.of(
                        "role", role,
                        "allowedSources", RoleAccess.getAllowedSources(role)
                ))
                .toList();
        return ResponseEntity.ok(Map.of("roles", rolesInfo));
    }

    // ─── Helpers ─────────────────────────────────────────────────

    private String validatePassword(String password) {
        if (password.length() < 8) {
            return "Password must be at least 8 characters long";
        }
        if (!password.matches(".*[A-Z].*")) {
            return "Password must contain at least one uppercase letter";
        }
        if (!password.matches(".*[a-z].*")) {
            return "Password must contain at least one lowercase letter";
        }
        if (!password.matches(".*\\d.*")) {
            return "Password must contain at least one number";
        }
        return null;
    }

    private String getClientIp(HttpServletRequest request) {
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isBlank()) {
            return xff.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
