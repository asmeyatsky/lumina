"""
Agency Report Exporter Infrastructure

Architectural Intent:
- Concrete implementation of the ReportExportPort protocol
- PDF generation using a manual structure-building approach
- CSV export for data tables
- Applies white-label branding to all exported documents
"""

from __future__ import annotations

import csv
import io
import struct
import zlib
from datetime import datetime, UTC

from lumina.agency.domain.entities import ClientReport, WhiteLabelConfig


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex colour string to an (R, G, B) tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


class _PDFBuilder:
    """Minimal PDF document builder for report generation.

    Builds a valid PDF file structure manually with basic text formatting,
    without requiring reportlab or any external PDF library.
    """

    def __init__(self) -> None:
        self._objects: list[bytes] = []
        self._pages: list[int] = []
        self._current_page_content: list[str] = []
        self._page_width = 612  # US Letter width in points
        self._page_height = 792  # US Letter height in points
        self._margin = 72  # 1 inch margins
        self._y_position = self._page_height - self._margin
        self._font_size = 12

    def _add_object(self, content: bytes) -> int:
        """Add a PDF object and return its 1-based index."""
        self._objects.append(content)
        return len(self._objects)

    def set_font_size(self, size: int) -> None:
        """Set the current font size."""
        self._font_size = size

    def add_title(self, text: str) -> None:
        """Add a title line to the current page."""
        self._current_page_content.append(
            f"BT /F1 18 Tf {self._margin} {self._y_position} Td ({_pdf_escape(text)}) Tj ET"
        )
        self._y_position -= 28

    def add_heading(self, text: str) -> None:
        """Add a heading line to the current page."""
        self._current_page_content.append(
            f"BT /F1 14 Tf {self._margin} {self._y_position} Td ({_pdf_escape(text)}) Tj ET"
        )
        self._y_position -= 22

    def add_text(self, text: str) -> None:
        """Add a text line to the current page."""
        # Word-wrap long lines
        max_chars = 80
        while len(text) > max_chars:
            split_pos = text.rfind(" ", 0, max_chars)
            if split_pos == -1:
                split_pos = max_chars
            self._add_text_line(text[:split_pos])
            text = text[split_pos:].lstrip()
        if text:
            self._add_text_line(text)

    def _add_text_line(self, text: str) -> None:
        """Add a single line of text."""
        if self._y_position < self._margin + 40:
            self._flush_page()
        self._current_page_content.append(
            f"BT /F1 {self._font_size} Tf {self._margin} {self._y_position} Td ({_pdf_escape(text)}) Tj ET"
        )
        self._y_position -= self._font_size + 4

    def add_separator(self) -> None:
        """Add a horizontal separator line."""
        self._current_page_content.append(
            f"{self._margin} {self._y_position} m "
            f"{self._page_width - self._margin} {self._y_position} l S"
        )
        self._y_position -= 16

    def add_spacer(self, height: int = 12) -> None:
        """Add vertical space."""
        self._y_position -= height

    def _flush_page(self) -> None:
        """Finalise the current page and start a new one."""
        content_str = "\n".join(self._current_page_content)
        stream_obj_idx = self._add_object(
            f"<< /Length {len(content_str)} >>\nstream\n{content_str}\nendstream".encode()
        )
        page_obj_idx = self._add_object(
            f"<< /Type /Page /MediaBox [0 0 {self._page_width} {self._page_height}] "
            f"/Contents {stream_obj_idx} 0 R /Resources << /Font << /F1 2 0 R >> >> >>".encode()
        )
        self._pages.append(page_obj_idx)
        self._current_page_content = []
        self._y_position = self._page_height - self._margin

    def build(self) -> bytes:
        """Build and return the complete PDF document."""
        # Flush any remaining page content
        if self._current_page_content:
            self._flush_page()

        if not self._pages:
            # Add at least one empty page
            self._flush_page()

        # Build the PDF structure
        output = io.BytesIO()
        output.write(b"%PDF-1.4\n")

        # Object 1: Catalog
        offsets: list[int] = []

        # We need to pre-build to know page tree reference
        # Object 1: Catalog -> references Pages (object 3)
        # Object 2: Font
        # Object 3: Pages
        # Object 4+: Page content streams and page objects from _objects

        # Re-number everything
        catalog_data = b"<< /Type /Catalog /Pages 3 0 R >>"
        font_data = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

        page_refs = " ".join(f"{i} 0 R" for i in self._pages)
        pages_data = (
            f"<< /Type /Pages /Kids [{page_refs}] /Count {len(self._pages)} >>".encode()
        )

        # Update page objects to reference parent Pages object (3)
        for i, page_idx in enumerate(self._pages):
            old = self._objects[page_idx - 1]
            # Inject /Parent 3 0 R into page object
            updated = old.replace(b"/Type /Page", b"/Type /Page /Parent 3 0 R")
            self._objects[page_idx - 1] = updated

        # Write all objects
        all_objects = [catalog_data, font_data, pages_data] + self._objects

        for idx, obj_data in enumerate(all_objects, 1):
            offsets.append(output.tell())
            output.write(f"{idx} 0 obj\n".encode())
            output.write(obj_data)
            output.write(b"\nendobj\n")

        # Cross-reference table
        xref_offset = output.tell()
        output.write(b"xref\n")
        output.write(f"0 {len(all_objects) + 1}\n".encode())
        output.write(b"0000000000 65535 f \n")
        for offset in offsets:
            output.write(f"{offset:010d} 00000 n \n".encode())

        # Trailer
        output.write(b"trailer\n")
        output.write(f"<< /Size {len(all_objects) + 1} /Root 1 0 R >>\n".encode())
        output.write(b"startxref\n")
        output.write(f"{xref_offset}\n".encode())
        output.write(b"%%EOF\n")

        return output.getvalue()


def _pdf_escape(text: str) -> str:
    """Escape special characters for PDF text strings."""
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


class ReportExporter:
    """Concrete implementation of the ReportExportPort.

    Generates branded PDF reports and CSV data exports for agency clients.
    """

    async def export_pdf(
        self, report: ClientReport, branding: WhiteLabelConfig
    ) -> bytes:
        """Export a report as a branded PDF document.

        The PDF includes:
        - Executive summary
        - AVS trend chart placeholder
        - Citation highlights
        - Recommendations
        - Next steps
        - Branded header and footer

        Args:
            report: The client report to export.
            branding: The white-label configuration for branding.

        Returns:
            The PDF content as bytes.
        """
        pdf = _PDFBuilder()
        report_data = dict(report.data)

        # --- Header with branding ---
        pdf.add_title(branding.company_name)
        pdf.add_spacer(8)
        pdf.add_heading(report.title)
        pdf.add_separator()
        pdf.add_spacer(8)

        # --- Executive Summary ---
        exec_summary = report_data.get("executive_summary", {})
        if isinstance(exec_summary, dict):
            pdf.add_heading("Executive Summary")
            pdf.add_spacer(4)
            for key, value in exec_summary.items():
                pdf.add_text(f"  {key.replace('_', ' ').title()}: {value}")
            pdf.add_spacer(8)

        # --- AVS Trend Chart Placeholder ---
        avs_trend = report_data.get("avs_trend") or report_data.get("avs_trend_chart")
        if avs_trend:
            pdf.add_heading("AI Visibility Score Trend")
            pdf.add_spacer(4)
            pdf.add_text("[AVS Trend Chart — visual chart would be rendered here]")
            if isinstance(avs_trend, dict):
                components = avs_trend.get("components", [])
                if isinstance(components, list):
                    for comp in components:
                        if isinstance(comp, dict):
                            module = comp.get("module", "")
                            score = comp.get("score", 0)
                            pdf.add_text(f"  {module}: {score}")
            pdf.add_spacer(8)

        # --- Citation Highlights ---
        citations = report_data.get("citation_highlights", {})
        if citations and isinstance(citations, dict):
            pdf.add_heading("Citation Highlights")
            pdf.add_spacer(4)
            for key, value in citations.items():
                pdf.add_text(f"  {key}: {value}")
            pdf.add_spacer(8)

        # --- Recommendations ---
        recommendations = report_data.get("recommendations", [])
        if recommendations and isinstance(recommendations, list):
            pdf.add_heading("Recommendations")
            pdf.add_spacer(4)
            for idx, rec in enumerate(recommendations, 1):
                if isinstance(rec, dict):
                    action = rec.get("action", "")
                    impact = rec.get("impact", "")
                    effort = rec.get("effort", "")
                    pdf.add_text(
                        f"  {idx}. {action} (Impact: {impact}, Effort: {effort})"
                    )
                else:
                    pdf.add_text(f"  {idx}. {rec}")
            pdf.add_spacer(8)

        # --- Next Steps ---
        next_steps = report_data.get("next_steps", [])
        if next_steps and isinstance(next_steps, list):
            pdf.add_heading("Next Steps")
            pdf.add_spacer(4)
            for idx, step in enumerate(next_steps, 1):
                pdf.add_text(f"  {idx}. {step}")
            pdf.add_spacer(8)

        # --- Content Performance (monthly) ---
        content_perf = report_data.get("content_performance")
        if content_perf and isinstance(content_perf, dict):
            pdf.add_heading("Content Performance")
            pdf.add_spacer(4)
            total = content_perf.get("total_assets_scored", 0)
            pdf.add_text(f"  Total assets scored: {total}")
            pdf.add_spacer(8)

        # --- Distribution Coverage (monthly) ---
        dist_coverage = report_data.get("distribution_coverage")
        if dist_coverage and isinstance(dist_coverage, dict):
            pdf.add_heading("Distribution Coverage")
            pdf.add_spacer(4)
            for key, value in dist_coverage.items():
                pdf.add_text(f"  {key}: {value}")
            pdf.add_spacer(8)

        # --- Footer ---
        pdf.add_separator()
        if branding.report_footer_text:
            pdf.add_text(branding.report_footer_text)
        if branding.powered_by_visible:
            pdf.add_text("Powered by LUMINA")
        pdf.add_text(f"Generated: {report.generated_at.strftime('%B %d, %Y at %H:%M UTC')}")

        return pdf.build()

    async def export_csv(self, data: dict[str, object]) -> bytes:
        """Export report data as CSV.

        Flattens nested data structures into rows suitable for CSV output.

        Args:
            data: The data to export.

        Returns:
            The CSV content as bytes.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(["Section", "Key", "Value"])

        for section_name, section_data in data.items():
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    writer.writerow([section_name, key, str(value)])
            elif isinstance(section_data, list):
                for idx, item in enumerate(section_data):
                    if isinstance(item, dict):
                        for key, value in item.items():
                            writer.writerow(
                                [f"{section_name}[{idx}]", key, str(value)]
                            )
                    else:
                        writer.writerow([section_name, str(idx), str(item)])
            else:
                writer.writerow([section_name, "", str(section_data)])

        return output.getvalue().encode("utf-8")
