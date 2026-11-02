from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ImageTk
import qrcode

from bookledger.services.mobile_connection import (
    MobileConnectionService,
    encode_pairing_qr,
)


class MobileAppSetupPanel(ttk.Frame):
    """Settings view for the local Android pairing service."""

    def __init__(self, parent, service: MobileConnectionService):
        super().__init__(parent)
        self.service = service
        self._qr_image = None
        self._last_qr_payload = None
        self._refresh_after_id = None
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(
            self,
            text="BookLedger Companion",
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.status_var = tk.StringVar(value="Starting local service…")
        ttk.Label(self, textvariable=self.status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 12)
        )

        address_frame = ttk.LabelFrame(self, text="Available IPv4 addresses", padding=10)
        address_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        self.addresses_var = tk.StringVar(value="Searching network interfaces…")
        ttk.Label(
            address_frame,
            textvariable=self.addresses_var,
            justify="left",
            wraplength=420,
        ).pack(anchor="nw")
        self.discovery_var = tk.StringVar(value="DNS-SD discovery: starting")
        ttk.Label(address_frame, textvariable=self.discovery_var).pack(
            anchor="nw", pady=(8, 0)
        )

        pairing_frame = ttk.LabelFrame(self, text="Pair Android companion", padding=10)
        pairing_frame.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        self.qr_label = ttk.Label(pairing_frame, text="Waiting for service…", anchor="center")
        self.qr_label.pack(fill="both", expand=True)
        self.credential_var = tk.StringVar()
        self.credential_label = ttk.Label(
            pairing_frame,
            textvariable=self.credential_var,
            font=("Consolas", 9),
            wraplength=380,
            justify="center",
        )
        self.credential_label.pack(fill="x", pady=(8, 4))

        actions = ttk.Frame(pairing_frame)
        actions.pack(fill="x")
        self.copy_button = ttk.Button(
            actions, text="Copy pairing code", command=self._copy_credential
        )
        self.copy_button.pack(side="left")
        self.refresh_button = ttk.Button(
            actions, text="New pairing code", command=self._refresh_credential
        )
        self.refresh_button.pack(side="left", padx=(8, 0))
        self.unpair_button = ttk.Button(
            actions, text="Unpair device", command=self._unpair
        )
        self.unpair_button.pack(side="right")

        ttk.Label(
            self,
            text=(
                "Connect the phone to the same Wi-Fi network, or to this PC's hotspot. "
                "If Windows Firewall asks, allow BookLedger on Private networks. "
                "BookLedger does not change firewall rules."
            ),
            wraplength=850,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 4))
        ttk.Label(
            self,
            text=(
                "Pairing uses HTTP on the local network. Traffic is not encrypted, "
                "so a network observer could read credentials. Use a trusted network."
            ),
            wraplength=850,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.service.start()
        self._refresh_after_id = self.after(250, self._refresh_view)

    def _refresh_view(self):
        self._refresh_after_id = None
        if not self.winfo_exists():
            return

        status = self.service.status
        discovery_status = self.service.discovery_status
        self.discovery_var.set(f"DNS-SD discovery: {discovery_status}")
        if status == "starting":
            self.status_var.set("Starting local service…")
        elif status == "ready":
            self.status_var.set("Ready for pairing")
        elif status == "paired":
            self.status_var.set(f"Paired with {self.service.paired_device_name}")
        elif status == "error":
            self.status_var.set(f"Service error: {self.service.error}")
        elif status == "stopping":
            self.status_var.set("Stopping local service…")
        else:
            self.status_var.set("Service inactive")

        candidates = self.service.candidates
        if candidates:
            self.addresses_var.set(
                "\n".join(
                    f"{item.interface}: {item.address}:{self.service.active_port}"
                    for item in candidates
                )
            )
        elif status in ("ready", "paired", "error"):
            self.addresses_var.set(
                "No usable private IPv4 address was found. Check that Wi-Fi or the "
                "Windows hotspot is connected."
            )
        else:
            self.addresses_var.set("Searching network interfaces…")

        credential = self.service.pairing_credential
        if self.service.paired:
            self.credential_var.set(
                f"This computer is paired with {self.service.paired_device_name}."
            )
            self.qr_label.configure(image="", text="Already paired")
            self._qr_image = None
            self.copy_button.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            self.unpair_button.configure(state="normal")
        elif credential and candidates and status == "ready":
            self.credential_var.set(
                f"Manual pairing code (expires in {self._remaining_seconds()} seconds):\n{credential}"
            )
            payload = encode_pairing_qr(
                candidates,
                self.service.active_port,
                credential,
            )
            self._show_qr(payload)
            self.copy_button.configure(state="normal")
            self.refresh_button.configure(state="disabled")
            self.unpair_button.configure(state="disabled")
        elif self.service.needs_pairing_reset:
            self.credential_var.set(
                "The saved token cannot be opened on this Windows account. "
                "Forget the saved pairing to pair again."
            )
            self.qr_label.configure(image="", text="Saved pairing needs attention")
            self._qr_image = None
            self.copy_button.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            self.unpair_button.configure(
                text="Forget saved pairing",
                state="normal",
            )
        elif status == "ready":
            self.credential_var.set(
                "Pairing code expired. Generate a new code."
                if candidates
                else ""
            )
            self.qr_label.configure(
                image="",
                text=(
                    "Create a new pairing code"
                    if candidates
                    else "No network address available"
                ),
            )
            self._qr_image = None
            self._last_qr_payload = None
            self.copy_button.configure(state="disabled")
            self.refresh_button.configure(
                state="normal" if candidates and not credential else "disabled"
            )
            self.unpair_button.configure(text="Unpair device", state="disabled")
        else:
            self.credential_var.set("")
            self.qr_label.configure(image="", text="Waiting for service…")
            self._qr_image = None
            self.copy_button.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            self.unpair_button.configure(text="Unpair device", state="disabled")

        if (
            not credential
            and not self.service.paired
            and status == "ready"
        ):
            self.refresh_button.configure(state="normal")
        self._refresh_after_id = self.after(1000, self._refresh_view)

    def _remaining_seconds(self) -> int:
        return max(0, int(self.service.pairing_expires_at - time.monotonic()))

    def _show_qr(self, payload: str):
        if payload == self._last_qr_payload:
            return
        code = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=4,
        )
        code.add_data(payload)
        code.make(fit=True)
        image = code.make_image(fill_color="black", back_color="white").convert("RGB")
        self._qr_image = ImageTk.PhotoImage(image, master=self)
        self.qr_label.configure(image=self._qr_image, text="")
        self._last_qr_payload = payload

    def _copy_credential(self):
        credential = self.service.pairing_credential
        if not credential:
            return
        self.clipboard_clear()
        self.clipboard_append(credential)
        self.status_var.set("Pairing code copied. It expires shortly.")

    def _refresh_credential(self):
        if not self.service.refresh_pairing_credential():
            self.status_var.set("Could not create a new pairing code.")
        self._last_qr_payload = None

    def _unpair(self):
        if not self.service.paired and not self.service.needs_pairing_reset:
            return
        title = (
            "Forget saved pairing?"
            if self.service.needs_pairing_reset
            else "Unpair mobile device?"
        )
        detail = (
            "The saved token cannot be used. Remove it before pairing this computer again."
            if self.service.needs_pairing_reset
            else "This revokes the saved mobile token. The phone will need to pair again."
        )
        if not messagebox.askyesno(title, detail, parent=self):
            return
        try:
            self.service.unpair()
        except Exception as exc:
            self.status_var.set(
                f"Could not unpair the mobile device ({type(exc).__name__})."
            )
            return
        self._last_qr_payload = None
        self.status_var.set("Mobile device unpaired. Ready for a new pairing.")

    def destroy(self):
        if self._refresh_after_id is not None:
            try:
                self.after_cancel(self._refresh_after_id)
            except tk.TclError:
                pass
            self._refresh_after_id = None
        super().destroy()
