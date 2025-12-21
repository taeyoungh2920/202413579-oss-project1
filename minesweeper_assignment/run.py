"""
Pygame presentation layer for Minesweeper.

This module owns:
- Renderer: all drawing of cells, header, and result overlays
- InputController: translate mouse input to board actions and UI feedback
- Game: orchestration of loop, timing, state transitions, and composition

The logic lives in components.Board; this module should not implement rules.
"""

import pygame
import random

import config
from components import Board
from pygame.locals import Rect


class Renderer:
    """Draws the Minesweeper UI.

    Knows how to draw individual cells with flags/numbers, header info,
    and end-of-game overlays with a semi-transparent background.
    """

    def __init__(self, screen: pygame.Surface, board: Board):
        self.screen = screen
        self.board = board
        self.font = pygame.font.Font(config.font_name, config.font_size)
        self.header_font = pygame.font.Font(config.font_name, config.header_font_size)
        self.result_font = pygame.font.Font(config.font_name, config.result_font_size)

    def cell_rect(self, col: int, row: int) -> Rect:
        """Return the rectangle in pixels for the given grid cell."""
        x = config.margin_left + col * config.cell_size
        y = config.margin_top + row * config.cell_size
        return Rect(x, y, config.cell_size, config.cell_size)

    def draw_cell(self, col: int, row: int, highlighted: bool) -> None:
        """Draw a single cell, respecting revealed/flagged state and highlight."""
        cell = self.board.cells[self.board.index(col, row)]
        rect = self.cell_rect(col, row)

        if cell.state.is_revealed:
            pygame.draw.rect(self.screen, config.color_cell_revealed, rect)

            if cell.state.is_mine:
                pygame.draw.circle(
                    self.screen,
                    config.color_cell_mine,
                    rect.center,
                    rect.width // 4,
                )
            elif cell.state.adjacent > 0:
                color = config.number_colors.get(cell.state.adjacent, config.color_text)
                label = self.font.render(str(cell.state.adjacent), True, color)
                label_rect = label.get_rect(center=rect.center)
                self.screen.blit(label, label_rect)

        else:
            base_color = config.color_highlight if highlighted else config.color_cell_hidden
            pygame.draw.rect(self.screen, base_color, rect)

            if cell.state.is_flagged:
                flag_w = max(6, rect.width // 3)
                flag_h = max(8, rect.height // 2)
                pole_x = rect.left + rect.width // 3
                pole_y = rect.top + 4

                pygame.draw.line(
                    self.screen,
                    config.color_flag,
                    (pole_x, pole_y),
                    (pole_x, pole_y + flag_h),
                    2,
                )
                pygame.draw.polygon(
                    self.screen,
                    config.color_flag,
                    [
                        (pole_x + 2, pole_y),
                        (pole_x + 2 + flag_w, pole_y + flag_h // 3),
                        (pole_x + 2, pole_y + flag_h // 2),
                    ],
                )

        pygame.draw.rect(self.screen, config.color_grid, rect, 1)

    def draw_header(self, remaining_mines: int, time_text: str) -> None:
        """Draw the header bar containing remaining mines and elapsed time."""
        pygame.draw.rect(
            self.screen,
            config.color_header,
            Rect(0, 0, config.width, config.margin_top - 4),
        )

        left_text = f"Mines: {remaining_mines}"
        right_text = f"Time: {time_text}"

        left_label = self.header_font.render(left_text, True, config.color_header_text)
        right_label = self.header_font.render(right_text, True, config.color_header_text)

        self.screen.blit(left_label, (10, 12))
        self.screen.blit(right_label, (config.width - right_label.get_width() - 10, 12))

    def draw_result_overlay(
        self,
        text: str | None,
        clear_time_sec: int | None,
        best_time_sec: int | None,
        difficulty: str | None,
    ) -> None:
        """Draw a semi-transparent overlay with centered result text, if any."""
        if not text:
            return

        overlay = pygame.Surface((config.width, config.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, config.result_overlay_alpha))
        self.screen.blit(overlay, (0, 0))

        # Main result text
        label = self.result_font.render(text, True, config.color_result)
        rect = label.get_rect(center=(config.width // 2, config.height // 2))
        self.screen.blit(label, rect)

        # Extra lines
        y = config.height // 2 + 40

        if clear_time_sec is not None:
            time_label = self.font.render(
                f"Time: {clear_time_sec}s",
                True,
                config.color_text_inv,
            )
            self.screen.blit(
                time_label,
                (config.width // 2 - time_label.get_width() // 2, y),
            )
            y += 30

        if best_time_sec is not None and difficulty is not None:
            best_label = self.font.render(
                f"Best ({difficulty}): {best_time_sec}s",
                True,
                config.color_text_inv,
            )
            self.screen.blit(
                best_label,
                (config.width // 2 - best_label.get_width() // 2, y),
            )

    def draw_difficulty_hint(self) -> None:
        text = "1: Easy   2: Normal   3: Hard"
        label = self.font.render(text, True, config.color_text_inv)
        rect = label.get_rect(center=(config.width // 2, config.margin_top // 2))
        self.screen.blit(label, rect)

class InputController:
    """Translates input events into game and board actions."""

    def __init__(self, game: "Game"):
        self.game = game

    def pos_to_grid(self, x: int, y: int):
        """Convert pixel coordinates to (col,row) or (-1,-1) if out of bounds."""
        if not (config.margin_left <= x < config.width - config.margin_right):
            return -1, -1
        if not (config.margin_top <= y < config.height - config.margin_bottom):
            return -1, -1

        col = (x - config.margin_left) // config.cell_size
        row = (y - config.margin_top) // config.cell_size

        if 0 <= col < self.game.board.cols and 0 <= row < self.game.board.rows:
            return int(col), int(row)
        return -1, -1

    def handle_mouse(self, pos, button) -> None:
        col, row = self.pos_to_grid(pos[0], pos[1])
        if col == -1:
            return

        game = self.game

        # LEFT CLICK: reveal
        if button == config.mouse_left:
            game.highlight_targets.clear()

            if not game.started:
                game.started = True
                game.start_ticks_ms = pygame.time.get_ticks()

            game.board.reveal(col, row)

        # RIGHT CLICK: toggle flag
        elif button == config.mouse_right:
            game.highlight_targets.clear()
            game.board.toggle_flag(col, row)

        # MIDDLE CLICK: highlight neighbors
        elif button == config.mouse_middle:
            try:
                neighbors = game.board.neighbors(col, row)
            except Exception:
                neighbors = []

            game.highlight_targets = {
                (nc, nr)
                for nc, nr in neighbors
                if not game.board.cells[game.board.index(nc, nr)].state.is_revealed
            }

            game.highlight_until_ms = pygame.time.get_ticks() + config.highlight_duration_ms


class Game:
    """Main application object orchestrating loop and high-level state."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(config.title)

        # 초기 화면(이후 create_board에서 난이도에 맞게 다시 설정됨)
        self.screen = pygame.display.set_mode(config.display_dimension)
        self.clock = pygame.time.Clock()

        # 난이도
        self.difficulty = config.default_difficulty  # config 그대로 사용
        self.create_board()

        self.renderer = Renderer(self.screen, self.board)
        self.input = InputController(self)

        self.highlight_targets = set()
        self.highlight_until_ms = 0

        self.started = False
        self.start_ticks_ms = 0
        self.end_ticks_ms = 0

        # Hint (3회 제한)
        self.hints_left = 3

        # High score (memory only, 난이도별 최단 시간, 초 단위)
        self.high_score = {
            "Easy": None,
            "Normal": None,
            "Hard": None,
        }

    def create_board(self):
        """Create board based on current difficulty and resize window."""
        d = config.difficulties[self.difficulty]
        self.board = Board(d["cols"], d["rows"], d["mines"])

        # 창 크기 재계산 (config 값 갱신)
        config.width = config.margin_left + d["cols"] * config.cell_size + config.margin_right
        config.height = config.margin_top + d["rows"] * config.cell_size + config.margin_bottom
        config.display_dimension = (config.width, config.height)

        # 화면 재설정
        self.screen = pygame.display.set_mode(config.display_dimension)

        # renderer가 이미 있으면 screen 업데이트
        if hasattr(self, "renderer"):
            self.renderer.screen = self.screen

    def reset(self):
        """Reset the game state and start a new board. (난이도 유지)"""
        self.create_board()
        self.renderer.board = self.board

        self.highlight_targets.clear()
        self.highlight_until_ms = 0

        self.started = False
        self.start_ticks_ms = 0
        self.end_ticks_ms = 0

        # 힌트는 새 게임마다 3회로
        self.hints_left = 3

        # 하이 스코어는 프로그램 실행 중 계속 유지 (reset 때 초기화하지 않음)

    def hint(self):
        """Reveal one random non-mine, unrevealed cell (max 3)."""
        if self.hints_left <= 0:
            return
        if self.board.game_over or self.board.win:
            return

        # 힌트도 '첫 행동'으로 취급해서 타이머 시작
        if not self.started:
            self.started = True
            self.start_ticks_ms = pygame.time.get_ticks()

        # 지뢰 X, 아직 안 열린 칸만
        candidates = [
            cell
            for cell in self.board.cells
            if (not cell.state.is_mine) and (not cell.state.is_revealed)
        ]
        if not candidates:
            return

        cell = random.choice(candidates)
        self.board.reveal(cell.col, cell.row)
        self.hints_left -= 1

    def _elapsed_ms(self) -> int:
        """Return elapsed time in milliseconds (stops when game ends)."""
        if not self.started:
            return 0
        if self.end_ticks_ms:
            return self.end_ticks_ms - self.start_ticks_ms
        return pygame.time.get_ticks() - self.start_ticks_ms

    def _format_time(self, ms: int) -> str:
        """Format milliseconds as mm:ss string."""
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _result_text(self) -> str | None:
        """Return result label to display, or None if game continues."""
        if self.board.game_over:
            return "GAME OVER"
        if self.board.win:
            return "GAME CLEAR"
        return None

    def draw(self):
        """Render one frame: header, grid, result overlay."""
        if pygame.time.get_ticks() > self.highlight_until_ms and self.highlight_targets:
            self.highlight_targets.clear()

        self.screen.fill(config.color_bg)

        remaining = max(0, self.board.num_mines - self.board.flagged_count())
        time_text = self._format_time(self._elapsed_ms())
        self.renderer.draw_header(remaining, time_text)

        if not self.started and not self.board.game_over and not self.board.win:
            self.renderer.draw_difficulty_hint()

        now = pygame.time.get_ticks()
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                highlighted = (now <= self.highlight_until_ms) and ((c, r) in self.highlight_targets)
                self.renderer.draw_cell(c, r, highlighted)

        result = self._result_text()
        if result:
            clear_time_sec = self._elapsed_ms() // 1000
            best_time_sec = self.high_score.get(self.difficulty)
            self.renderer.draw_result_overlay(result, clear_time_sec, best_time_sec, self.difficulty)
        else:
            self.renderer.draw_result_overlay(None, None, None, None)

        pygame.display.flip()

    def run_step(self) -> bool:
        """Process inputs, update time, draw, and tick the clock once."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # 1 = Easy, 2 = Normal, 3 = Hard
            # R = Restart, H = Hint
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    self.difficulty = "Easy"
                    self.reset()
                elif event.key == pygame.K_2:
                    self.difficulty = "Normal"
                    self.reset()
                elif event.key == pygame.K_3:
                    self.difficulty = "Hard"
                    self.reset()
                elif event.key == pygame.K_r:
                    self.reset()
                elif event.key == pygame.K_h:
                    self.hint()

            if event.type == pygame.MOUSEBUTTONDOWN:
                self.input.handle_mouse(event.pos, event.button)

        # 게임 종료 순간(한 번만) 시간 고정 + 하이 스코어 갱신
        if (self.board.game_over or self.board.win) and self.started and not self.end_ticks_ms:
            self.end_ticks_ms = pygame.time.get_ticks()

            if self.board.win:
                clear_time_sec = self._elapsed_ms() // 1000
                best = self.high_score.get(self.difficulty)

                if best is None or clear_time_sec < best:
                    self.high_score[self.difficulty] = clear_time_sec

        self.draw()
        self.clock.tick(config.fps)
        return True


def main() -> int:
    """Application entrypoint: run the main loop until quit."""
    game = Game()
    running = True
    while running:
        running = game.run_step()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
