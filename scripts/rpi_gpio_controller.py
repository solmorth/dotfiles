#!/usr/bin/env python3
"""
Raspberry Pi GPIO Pin Visualizer and Controller
This script provides a terminal-based interface to visualize and control GPIO pins
"""

import sys
import os
import json
import shutil

# Try to import RPi.GPIO, fallback to mock for testing on non-RPi systems
try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except (ImportError, RuntimeError):
    print("RPi.GPIO not available. Running in MOCK mode for testing.")
    MOCK_MODE = True
    
    # Mock GPIO module for testing on non-RPi systems
    class MockGPIO:
        BCM = "BCM"
        BOARD = "BOARD"
        IN = "IN"
        OUT = "OUT"
        HIGH = 1
        LOW = 0
        PUD_UP = "PUD_UP"
        PUD_DOWN = "PUD_DOWN"
        
        _mode = None
        _pins = {}
        
        @classmethod
        def setmode(cls, mode):
            cls._mode = mode
        
        @classmethod
        def setup(cls, pin, direction, pull_up_down=None):
            cls._pins[pin] = {'direction': direction, 'state': cls.LOW, 'pull': pull_up_down}
        
        @classmethod
        def output(cls, pin, state):
            if pin in cls._pins:
                cls._pins[pin]['state'] = state
        
        @classmethod
        def input(cls, pin):
            return cls._pins.get(pin, {}).get('state', cls.LOW)
        
        @classmethod
        def cleanup(cls):
            cls._pins.clear()
        
        @classmethod
        def getmode(cls):
            return cls._mode
    
    GPIO = MockGPIO()


# ANSI color codes for terminal
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class GPIOController:
    """Terminal-based application class for GPIO visualization and control"""
    
    # GPIO pin mapping (BCM numbering to physical pin)
    # Format: physical_pin: (BCM_number, name, default_function)
    PIN_MAP = {
        1: (None, "3.3V", "Power"),
        2: (None, "5V", "Power"),
        3: (2, "GPIO2", "I2C SDA"),
        4: (None, "5V", "Power"),
        5: (3, "GPIO3", "I2C SCL"),
        6: (None, "GND", "Ground"),
        7: (4, "GPIO4", "GPCLK0"),
        8: (14, "GPIO14", "UART TX"),
        9: (None, "GND", "Ground"),
        10: (15, "GPIO15", "UART RX"),
        11: (17, "GPIO17", "GPIO"),
        12: (18, "GPIO18", "PWM0"),
        13: (27, "GPIO27", "GPIO"),
        14: (None, "GND", "Ground"),
        15: (22, "GPIO22", "GPIO"),
        16: (23, "GPIO23", "GPIO"),
        17: (None, "3.3V", "Power"),
        18: (24, "GPIO24", "GPIO"),
        19: (10, "GPIO10", "SPI MOSI"),
        20: (None, "GND", "Ground"),
        21: (9, "GPIO9", "SPI MISO"),
        22: (25, "GPIO25", "GPIO"),
        23: (11, "GPIO11", "SPI SCLK"),
        24: (8, "GPIO8", "SPI CE0"),
        25: (None, "GND", "Ground"),
        26: (7, "GPIO7", "SPI CE1"),
        27: (0, "GPIO0", "ID_SD"),
        28: (1, "GPIO1", "ID_SC"),
        29: (5, "GPIO5", "GPIO"),
        30: (None, "GND", "Ground"),
        31: (6, "GPIO6", "GPIO"),
        32: (12, "GPIO12", "PWM0"),
        33: (13, "GPIO13", "PWM1"),
        34: (None, "GND", "Ground"),
        35: (19, "GPIO19", "SPI MISO"),
        36: (16, "GPIO16", "GPIO"),
        37: (26, "GPIO26", "GPIO"),
        38: (20, "GPIO20", "SPI MOSI"),
        39: (None, "GND", "Ground"),
        40: (21, "GPIO21", "SPI SCLK"),
    }
    
    def __init__(self):
        # Initialize GPIO
        try:
            GPIO.setmode(GPIO.BCM)
        except:
            pass
        
        # Track configured pins
        self.configured_pins = {}
        
        # Config file path - follow XDG spec or fallback to ~/.config/ores/
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
        config_dir = os.path.join(xdg_config_home, 'ores')
        self.config_file = os.path.join(config_dir, 'gpio_config.json')

        # If an old config exists next to the script, migrate it to the XDG location
        old_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gpio_config.json')
        try:
            if os.path.exists(old_path) and not os.path.exists(self.config_file):
                os.makedirs(config_dir, exist_ok=True)
                try:
                    shutil.move(old_path, self.config_file)
                    print(f"{Colors.CYAN}Migrated config from {old_path} to {self.config_file}{Colors.RESET}")
                except Exception:
                    # fallback to copy
                    shutil.copy2(old_path, self.config_file)
                    print(f"{Colors.CYAN}Copied config from {old_path} to {self.config_file}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: failed to migrate config: {e}{Colors.RESET}")

        # Load saved configuration
        self.load_config()
    
    def save_config(self):
        """Save current pin configuration to file (excluding output states)"""
        try:
            config_data = {}
            for pin, cfg in self.configured_pins.items():
                config_data[str(pin)] = {
                    'direction': cfg['direction'],
                    'pull': cfg.get('pull', 'none'),
                    'name': cfg.get('name', '')
                    # Note: We don't save 'state' - outputs always start LOW
                }
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"{Colors.RED}Error saving config: {str(e)}{Colors.RESET}")
            return False
    
    def load_config(self):
        """Load pin configuration from file (outputs always start LOW)"""
        if not os.path.exists(self.config_file):
            return
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            for pin_str, cfg in config_data.items():
                pin = int(pin_str)
                
                # Setup the pin according to saved configuration
                try:
                    if cfg['direction'] == 'output':
                        GPIO.setup(pin, GPIO.OUT)
                        # Always initialize outputs to LOW
                        GPIO.output(pin, GPIO.LOW)
                        self.configured_pins[pin] = {
                            'direction': 'output',
                            'state': GPIO.LOW,
                            'name': cfg.get('name', '')
                        }
                    else:  # input
                        pull = cfg.get('pull', 'none')
                        if pull == 'up':
                            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                        elif pull == 'down':
                            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                        else:
                            GPIO.setup(pin, GPIO.IN)
                        
                        self.configured_pins[pin] = {
                            'direction': 'input',
                            'pull': pull,
                            'name': cfg.get('name', '')
                        }
                except Exception as e:
                    print(f"{Colors.YELLOW}Warning: Could not restore GPIO{pin}: {str(e)}{Colors.RESET}")
            
            if self.configured_pins:
                print(f"{Colors.GREEN}✓ Loaded configuration for {len(self.configured_pins)} pin(s){Colors.RESET}")
        
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not load config file: {str(e)}{Colors.RESET}")
    
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_pin_status_symbol(self, bcm_pin):
        """Get colored status symbol for a pin"""
        if bcm_pin not in self.configured_pins:
            return f"{Colors.GRAY}○{Colors.RESET}"
        
        config = self.configured_pins[bcm_pin]
        if config['direction'] == 'output':
            state = config.get('state', GPIO.LOW)
            if state == GPIO.HIGH:
                return f"{Colors.GREEN}●{Colors.RESET}"
            else:
                return f"{Colors.RED}●{Colors.RESET}"
        else:  # input
            try:
                state = GPIO.input(bcm_pin)
                if state:
                    return f"{Colors.BLUE}●{Colors.RESET}"
                else:
                    return f"{Colors.GRAY}●{Colors.RESET}"
            except:
                return f"{Colors.GRAY}○{Colors.RESET}"
    
    def display_pins(self):
        """Display GPIO pin layout"""
        self.clear_screen()
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}╔═══════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}║        Raspberry Pi GPIO Pin Controller (Terminal Mode)          ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}╚═══════════════════════════════════════════════════════════════════╝{Colors.RESET}\n")
        
        if MOCK_MODE:
            print(f"{Colors.YELLOW}[MOCK MODE - Testing on non-RPi system]{Colors.RESET}\n")
        else:
            print(f"{Colors.GREEN}[LIVE MODE - Raspberry Pi]{Colors.RESET}\n")
        
        print(f"{Colors.BOLD}Pin Layout:{Colors.RESET}\n")
        
        # Display pins in two columns
        for i in range(20):
            left_pin = i * 2 + 1
            right_pin = i * 2 + 2
            
            # Left pin
            bcm_left, name_left, func_left = self.PIN_MAP[left_pin]
            if bcm_left is None:
                if "GND" in name_left:
                    left_display = f"{Colors.GRAY}[{left_pin:02d}] {name_left:7} ({func_left:10}){Colors.RESET}"
                elif "3.3V" in name_left:
                    left_display = f"{Colors.YELLOW}[{left_pin:02d}] {name_left:7} ({func_left:10}){Colors.RESET}"
                elif "5V" in name_left:
                    left_display = f"{Colors.RED}[{left_pin:02d}] {name_left:7} ({func_left:10}){Colors.RESET}"
            else:
                status = self.get_pin_status_symbol(bcm_left)
                config_text = ""
                custom_name = ""
                if bcm_left in self.configured_pins:
                    cfg = self.configured_pins[bcm_left]
                    config_text = f" {Colors.CYAN}[{cfg['direction'][:3].upper()}]{Colors.RESET}"
                    if cfg.get('name'):
                        custom_name = f" {Colors.MAGENTA}'{cfg['name']}'{Colors.RESET}"
                left_display = f"{status} [{left_pin:02d}] {name_left:7} ({func_left:10}){config_text}{custom_name}"
            
            # Right pin
            bcm_right, name_right, func_right = self.PIN_MAP[right_pin]
            if bcm_right is None:
                if "GND" in name_right:
                    right_display = f"{Colors.GRAY}({func_right:10}) {name_right:7} [{right_pin:02d}]{Colors.RESET}"
                elif "3.3V" in name_right:
                    right_display = f"{Colors.YELLOW}({func_right:10}) {name_right:7} [{right_pin:02d}]{Colors.RESET}"
                elif "5V" in name_right:
                    right_display = f"{Colors.RED}({func_right:10}) {name_right:7} [{right_pin:02d}]{Colors.RESET}"
            else:
                status = self.get_pin_status_symbol(bcm_right)
                config_text = ""
                custom_name = ""
                if bcm_right in self.configured_pins:
                    cfg = self.configured_pins[bcm_right]
                    config_text = f"{Colors.CYAN}[{cfg['direction'][:3].upper()}]{Colors.RESET} "
                    if cfg.get('name'):
                        custom_name = f"{Colors.MAGENTA}'{cfg['name']}' {Colors.RESET}"
                right_display = f"{custom_name}{config_text}({func_right:10}) {name_right:7} [{right_pin:02d}] {status}"
            
            print(f"{left_display:90}  {right_display}")
        
        print(f"\n{Colors.BOLD}Legend:{Colors.RESET} {Colors.GREEN}●{Colors.RESET} OUT-HIGH  {Colors.RED}●{Colors.RESET} OUT-LOW  {Colors.BLUE}●{Colors.RESET} IN-HIGH  {Colors.GRAY}●{Colors.RESET} IN-LOW  {Colors.GRAY}○{Colors.RESET} Not Configured")
    
    def show_menu(self):
        """Display main menu"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}═══════════════════════════════════════════════════════════════════{Colors.RESET}")
        print(f"{Colors.BOLD}Main Menu:{Colors.RESET}")
        print("  1. Setup Pin (configure as input/output)")
        print("  2. Control Pin (read/write)")
        print("  3. Read All Inputs")
        print("  4. Set All Outputs HIGH")
        print("  5. Set All Outputs LOW")
        print("  6. Show Pin Details")
        print("  7. Rename Pin")
        print("  8. Cleanup All Pins")
        print("  0. Refresh Display")
        print("  q. Exit")
        print(f"{Colors.BOLD}{Colors.CYAN}═══════════════════════════════════════════════════════════════════{Colors.RESET}")
    
    def setup_pin(self):
        """Setup a GPIO pin"""
        try:
            bcm_pin = int(input(f"\n{Colors.BOLD}Enter BCM pin number to setup: {Colors.RESET}"))
            
            # Validate pin
            valid_pins = [bcm for bcm, _, _ in self.PIN_MAP.values() if bcm is not None]
            if bcm_pin not in valid_pins:
                print(f"{Colors.RED}Invalid GPIO pin number!{Colors.RESET}")
                return
            
            # Ask for custom name
            custom_name = input(f"Enter custom name for this pin (optional, press Enter to skip): ").strip()
            
            print(f"\n{Colors.BOLD}Configure GPIO{bcm_pin}:{Colors.RESET}")
            print("  1. Output")
            print("  2. Input (no pull)")
            print("  3. Input (pull-up)")
            print("  4. Input (pull-down)")
            
            choice = input("Select option: ").strip()
            
            if choice == "1":
                GPIO.setup(bcm_pin, GPIO.OUT)
                self.configured_pins[bcm_pin] = {'direction': 'output', 'state': GPIO.LOW, 'name': custom_name}
                GPIO.output(bcm_pin, GPIO.LOW)
                print(f"{Colors.GREEN}✓ GPIO{bcm_pin} configured as OUTPUT (initialized to LOW){Colors.RESET}")
            
            elif choice in ["2", "3", "4"]:
                if choice == "2":
                    GPIO.setup(bcm_pin, GPIO.IN)
                    pull = "none"
                elif choice == "3":
                    GPIO.setup(bcm_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    pull = "up"
                else:
                    GPIO.setup(bcm_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    pull = "down"
                
                self.configured_pins[bcm_pin] = {'direction': 'input', 'pull': pull, 'name': custom_name}
                print(f"{Colors.GREEN}✓ GPIO{bcm_pin} configured as INPUT (pull-{pull}){Colors.RESET}")
            else:
                print(f"{Colors.RED}Invalid option!{Colors.RESET}")
                return
            
            # Auto-save configuration after setup
            if self.save_config():
                print(f"{Colors.CYAN}✓ Configuration saved{Colors.RESET}")
        
        except ValueError:
            print(f"{Colors.RED}Invalid input!{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def control_pin(self):
        """Control a configured GPIO pin"""
        try:
            bcm_pin = int(input(f"\n{Colors.BOLD}Enter BCM pin number to control: {Colors.RESET}"))
            
            if bcm_pin not in self.configured_pins:
                print(f"{Colors.RED}Pin not configured! Please setup first.{Colors.RESET}")
                input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
                return
            
            config = self.configured_pins[bcm_pin]
            
            if config['direction'] == 'output':
                print(f"\n{Colors.BOLD}Control GPIO{bcm_pin} (OUTPUT):{Colors.RESET}")
                print("  1. Set HIGH")
                print("  2. Set LOW")
                print("  3. Toggle")
                
                choice = input("Select option: ").strip()
                
                if choice == "1":
                    GPIO.output(bcm_pin, GPIO.HIGH)
                    self.configured_pins[bcm_pin]['state'] = GPIO.HIGH
                    print(f"{Colors.GREEN}✓ GPIO{bcm_pin} set to HIGH{Colors.RESET}")
                    self.save_config()
                elif choice == "2":
                    GPIO.output(bcm_pin, GPIO.LOW)
                    self.configured_pins[bcm_pin]['state'] = GPIO.LOW
                    print(f"{Colors.GREEN}✓ GPIO{bcm_pin} set to LOW{Colors.RESET}")
                    self.save_config()
                elif choice == "3":
                    current = self.configured_pins[bcm_pin].get('state', GPIO.LOW)
                    new_state = GPIO.LOW if current == GPIO.HIGH else GPIO.HIGH
                    GPIO.output(bcm_pin, new_state)
                    self.configured_pins[bcm_pin]['state'] = new_state
                    state_text = "HIGH" if new_state == GPIO.HIGH else "LOW"
                    print(f"{Colors.GREEN}✓ GPIO{bcm_pin} toggled to {state_text}{Colors.RESET}")
                    self.save_config()
                else:
                    print(f"{Colors.RED}Invalid option!{Colors.RESET}")
            
            else:  # input
                print(f"\n{Colors.BOLD}Read GPIO{bcm_pin} (INPUT):{Colors.RESET}")
                state = GPIO.input(bcm_pin)
                state_text = "HIGH (1)" if state else "LOW (0)"
                color = Colors.GREEN if state else Colors.RED
                print(f"Current state: {color}{state_text}{Colors.RESET}")
                self.configured_pins[bcm_pin]['state'] = state
        
        except ValueError:
            print(f"{Colors.RED}Invalid input!{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def read_all_inputs(self):
        """Read all configured input pins"""
        input_pins = [pin for pin, config in self.configured_pins.items() 
                     if config['direction'] == 'input']
        
        if not input_pins:
            print(f"\n{Colors.YELLOW}No input pins configured!{Colors.RESET}")
        else:
            print(f"\n{Colors.BOLD}Input Pin States:{Colors.RESET}")
            for pin in sorted(input_pins):
                try:
                    state = GPIO.input(pin)
                    state_text = "HIGH" if state else "LOW"
                    color = Colors.GREEN if state else Colors.RED
                    self.configured_pins[pin]['state'] = state
                    print(f"  GPIO{pin:2d}: {color}{state_text}{Colors.RESET}")
                except Exception as e:
                    print(f"  GPIO{pin:2d}: {Colors.RED}Error - {str(e)}{Colors.RESET}")
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def set_all_outputs(self, state):
        """Set all configured output pins to specified state"""
        output_pins = [pin for pin, config in self.configured_pins.items() 
                      if config['direction'] == 'output']
        
        if not output_pins:
            print(f"\n{Colors.YELLOW}No output pins configured!{Colors.RESET}")
        else:
            state_text = "HIGH" if state == GPIO.HIGH else "LOW"
            print(f"\n{Colors.BOLD}Setting all outputs to {state_text}...{Colors.RESET}")
            for pin in sorted(output_pins):
                try:
                    GPIO.output(pin, state)
                    self.configured_pins[pin]['state'] = state
                    print(f"  GPIO{pin:2d}: {Colors.GREEN}✓{Colors.RESET}")
                except Exception as e:
                    print(f"  GPIO{pin:2d}: {Colors.RED}Error - {str(e)}{Colors.RESET}")
            print(f"{Colors.GREEN}Done!{Colors.RESET}")
            
            # Auto-save configuration
            self.save_config()
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def show_pin_details(self):
        """Show detailed information about configured pins"""
        if not self.configured_pins:
            print(f"\n{Colors.YELLOW}No pins configured yet!{Colors.RESET}")
        else:
            print(f"\n{Colors.BOLD}Configured Pins:{Colors.RESET}")
            print(f"{'BCM':>4} | {'Name':^15} | {'Direction':^10} | {'State':^10} | {'Pull':^10}")
            print("-" * 60)
            for pin in sorted(self.configured_pins.keys()):
                config = self.configured_pins[pin]
                direction = config['direction'].upper()
                name = config.get('name', '-')[:15]
                
                if config['direction'] == 'output':
                    state = "HIGH" if config.get('state') == GPIO.HIGH else "LOW"
                    pull = "N/A"
                else:
                    try:
                        state_val = GPIO.input(pin)
                        state = "HIGH" if state_val else "LOW"
                    except:
                        state = "ERROR"
                    pull = config.get('pull', 'none').upper()
                
                print(f"{pin:4} | {name:^15} | {direction:^10} | {state:^10} | {pull:^10}")
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def rename_pin(self):
        """Rename a configured pin"""
        try:
            bcm_pin = int(input(f"\n{Colors.BOLD}Enter BCM pin number to rename: {Colors.RESET}"))
            
            if bcm_pin not in self.configured_pins:
                print(f"{Colors.RED}Pin not configured! Please setup first.{Colors.RESET}")
                input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
                return
            
            current_name = self.configured_pins[bcm_pin].get('name', '')
            if current_name:
                print(f"Current name: {Colors.MAGENTA}'{current_name}'{Colors.RESET}")
            else:
                print("Current name: (none)")
            
            new_name = input(f"Enter new name (or press Enter to remove name): ").strip()
            self.configured_pins[bcm_pin]['name'] = new_name
            
            if new_name:
                print(f"{Colors.GREEN}✓ GPIO{bcm_pin} renamed to '{new_name}'{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}✓ GPIO{bcm_pin} name removed{Colors.RESET}")
            
            # Auto-save configuration
            if self.save_config():
                print(f"{Colors.CYAN}✓ Configuration saved{Colors.RESET}")
        
        except ValueError:
            print(f"{Colors.RED}Invalid input!{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def cleanup_all(self):
        """Cleanup all GPIO pins"""
        confirm = input(f"\n{Colors.YELLOW}Reset all GPIO pins to default state? (yes/no): {Colors.RESET}").strip().lower()
        
        if confirm in ['yes', 'y']:
            try:
                GPIO.cleanup()
                self.configured_pins.clear()
                
                # Save empty configuration
                self.save_config()
                
                print(f"{Colors.GREEN}✓ All GPIO pins cleaned up!{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        else:
            print("Cancelled.")
        
        input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
    
    def run(self):
        """Main application loop"""
        try:
            while True:
                self.display_pins()
                self.show_menu()
                
                choice = input(f"\n{Colors.BOLD}Enter your choice: {Colors.RESET}").strip().lower()
                
                if choice == "1":
                    self.setup_pin()
                elif choice == "2":
                    self.control_pin()
                elif choice == "3":
                    self.read_all_inputs()
                elif choice == "4":
                    self.set_all_outputs(GPIO.HIGH)
                elif choice == "5":
                    self.set_all_outputs(GPIO.LOW)
                elif choice == "6":
                    self.show_pin_details()
                elif choice == "7":
                    self.rename_pin()
                elif choice == "8":
                    self.cleanup_all()
                elif choice == "0":
                    continue  # Refresh display
                elif choice == "q":
                    print(f"\n{Colors.CYAN}Saving configuration and exiting...{Colors.RESET}")
                    self.save_config()
                    GPIO.cleanup()
                    break
                else:
                    print(f"{Colors.RED}Invalid choice!{Colors.RESET}")
                    input(f"\n{Colors.GRAY}Press Enter to continue...{Colors.RESET}")
        
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Interrupted by user.{Colors.RESET}")
            print(f"{Colors.CYAN}Saving configuration...{Colors.RESET}")
            self.save_config()
            GPIO.cleanup()
        except Exception as e:
            print(f"\n{Colors.RED}Fatal error: {str(e)}{Colors.RESET}")
            GPIO.cleanup()


def main():
    """Main entry point"""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║        Raspberry Pi GPIO Controller - Terminal Edition           ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print(Colors.RESET)
    
    app = GPIOController()
    app.run()


if __name__ == "__main__":
    main()
