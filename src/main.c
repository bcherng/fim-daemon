#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifdef _WIN32
#include <windows.h>
#endif

void run_daemon(const char *server_url) {
    while (1) {
        printf("FIM Daemon heartbeat -> %s\n", server_url);
        fflush(stdout);
        sleep(30);
    }
}

int main(int argc, char *argv[]) {
    const char *server_url = "18.188.156.219";
    if (argc > 1 && strcmp(argv[1], "--server") == 0 && argc > 2) {
        server_url = argv[2];
    }

    printf("Starting FIM Daemon. Reporting to %s\n", server_url);
    run_daemon(server_url);
    return 0;
}
