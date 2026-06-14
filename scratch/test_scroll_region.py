import sys
import time
import shutil

def test():
    _, rows = shutil.get_terminal_size((80, 24))
    if rows < 10:
        print("Terminal too small.")
        return

    print("Welcome to scroll test.")
    print("This content should scroll.")

    # Set scroll region: lines 1 to rows - 2
    # Format: \033[top;bottomr
    sys.stdout.write(f"\033[1;{rows-2}r")
    sys.stdout.flush()

    # Draw frozen footer
    def draw_footer():
        sys.stdout.write("\033[s") # Save cursor
        sys.stdout.write(f"\033[{rows-1};1H\033[K") # Go to second to last line, clear line
        sys.stdout.write("-" * 80)
        sys.stdout.write(f"\033[{rows};1H\033[K") # Go to last line, clear line
        sys.stdout.write("Frozen Footer: ? for help · Ctrl+C to exit")
        sys.stdout.write("\033[u") # Restore cursor
        sys.stdout.flush()

    draw_footer()

    # Stream some lines that will trigger scroll
    for i in range(1, 30):
        print(f"Streaming line {i}...")
        sys.stdout.flush()
        time.sleep(0.1)

    # Reset scroll region
    sys.stdout.write("\033[r")
    # Move to the very bottom and print done
    sys.stdout.write(f"\033[{rows};1H\n")
    print("Done!")

if __name__ == "__main__":
    test()
