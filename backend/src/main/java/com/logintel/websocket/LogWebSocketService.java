package com.logintel.websocket;

import com.logintel.model.LogEntry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

/**
 * Broadcasts new log entries to all connected WebSocket clients.
 *
 * Called by LogConsumerService after each log is indexed to Elasticsearch.
 * Clients subscribe to /topic/logs to receive real-time updates.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class LogWebSocketService {

    private final SimpMessagingTemplate messagingTemplate;

    /**
     * Sends a log entry to all subscribed WebSocket clients.
     */
    public void broadcastLog(LogEntry logEntry) {
        try {
            messagingTemplate.convertAndSend("/topic/logs", logEntry);
        } catch (Exception e) {
            log.debug("WebSocket broadcast failed (no clients connected): {}", e.getMessage());
        }
    }
}
