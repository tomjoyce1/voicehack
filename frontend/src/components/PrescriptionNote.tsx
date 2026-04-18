"use client";

import { Printer } from "lucide-react";
import styles from "./PrescriptionNote.module.css";

export type PrescriptionMedication = {
  name: string;
  dose: string;
  form: string;
  quantity: string;
  instructions: string;
};

export type PrescriptionData = {
  patientName: string;
  patientAge: string;
  patientAddress: string;
  medications: PrescriptionMedication[];
  date: string;
};

type Props = {
  prescription: PrescriptionData;
  layout?: "full" | "sidebar";
};

export function PrescriptionNote({ prescription, layout = "full" }: Props) {
  const { patientName, patientAge, patientAddress, medications, date } = prescription;

  const handlePrint = () => {
    window.print();
  };

  const rootClass =
    layout === "sidebar" ? `${styles.watermark} ${styles.sidebar}` : styles.watermark;

  return (
    <div className={rootClass}>
      <div className={`${styles.form} prescription-note-form`} data-prescription-root>
        <div className={styles.topTitle}>
          <div>
            <strong className={styles.printedTitle}>NHS PRESCRIPTION FORM (FP10)</strong>
            <div className={`${styles.handwritten} ${styles.topSubtitle}`}>
              Prescriber copy · Simulated patient record
            </div>
          </div>
          <div className={`${styles.fpRef} ${styles.handwritten}`}>
            FP10
            <div className={styles.fpTrn}>TRN</div>
          </div>
        </div>

        <div className={styles.grid2}>
          <div className={styles.patientBlock}>
            <div className={styles.sectionHead}>Patient details</div>
            <div className={styles.row}>
              <div className={styles.label}>Name</div>
              <div className={`${styles.value} ${styles.handwritten}`}>{patientName}</div>
            </div>
            <div className={styles.row}>
              <div className={styles.label}>Age</div>
              <div className={`${styles.value} ${styles.handwritten}`}>{patientAge}</div>
            </div>
            <div className={`${styles.row} ${styles.rowTall}`}>
              <div className={styles.label}>Address</div>
              <div className={`${styles.value} ${styles.handwritten}`} style={{ whiteSpace: "pre-line" }}>
                {patientAddress}
              </div>
            </div>
          </div>
          <div className={styles.sideCol}>
            <div className={styles.sideCell}>
              <div className={styles.miniLabel}>NHS No. (sim)</div>
              <div className={`${styles.handwritten} ${styles.nhsPlaceholder}`}>### ### ####</div>
            </div>
            <div className={styles.sideCell}>
              <div className={styles.miniLabel}>Date issued</div>
              <div className={styles.handwritten}>{date}</div>
            </div>
          </div>
        </div>

        <div className={styles.stampNpRow}>
          <div className={styles.stampBox}>
            <div className={styles.miniLabel}>Pharmacy stamp</div>
            <div className={styles.stampInner} aria-hidden />
          </div>
          <div className={styles.npBox}>
            <span className={styles.miniLabel} style={{ marginBottom: 4 }}>
              NP
            </span>
            <span className={styles.handwritten}>—</span>
          </div>
        </div>

        <div className={styles.endorsement}>
          <div className={styles.miniLabel}>Dispenser endorsement (NHS / exemption / charge)</div>
          <div className={`${styles.endorseGrid} ${styles.endorseGridMono}`} aria-hidden>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={styles.endorseCell} />
            ))}
          </div>
        </div>

        <div className={styles.sectionHead}>Prescription — prescribed items</div>
        {medications.length === 0 ? (
          <div className={styles.medBlock}>
            <p
              className={`${styles.medLine} ${styles.handwritten}`}
              style={{ borderLeftColor: "transparent", paddingLeft: 0 }}
            >
              No medications could be identified from your diagnosis wording. If drugs were
              intended, state them explicitly in the diagnosis or management statement.
            </p>
          </div>
        ) : (
          medications.map((m, idx) => (
            <div key={`${m.name}-${idx}`} className={styles.medBlock}>
              <div className={`${styles.medName} ${styles.handwritten}`}>{m.name}</div>
              <div className={`${styles.medLine} ${styles.handwritten}`}>
                {m.dose}
                {m.form ? ` · ${m.form}` : ""}
                {m.quantity ? ` · Qty: ${m.quantity}` : ""}
              </div>
              <div className={`${styles.medLine} ${styles.handwritten}`}>{m.instructions || "—"}</div>
            </div>
          ))
        )}

        <div className={styles.nhsFooter}>TRAINING FORM ONLY — NOT VALID FOR DISPENSING</div>
      </div>

      <div className={styles.badge}>Parsed from your consultation wording</div>

      <div className={styles.downloadWrap}>
        <button type="button" className={styles.downloadBtn} onClick={handlePrint}>
          <Printer className="h-4 w-4" aria-hidden />
          Download as PDF
        </button>
        <p className={styles.printHelp}>
          Uses your browser&apos;s print dialog — choose &quot;Save as PDF&quot; to download. Other page
          content is hidden while printing.
        </p>
      </div>
    </div>
  );
}
