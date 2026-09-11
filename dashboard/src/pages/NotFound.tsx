// 404 — page not found.
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] } },
};

export default function NotFound() {
  return (
    <motion.div className="not-found" variants={fadeUp} initial="initial" animate="animate">
      <motion.span
        className="not-found-code"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.25, 0.1, 0.25, 1] }}
      >
        404
      </motion.span>
      <motion.h1
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.2 }}
      >
        Page not found
      </motion.h1>
      <motion.p
        className="muted"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35, delay: 0.3 }}
      >
        The page you're looking for doesn't exist or has been moved.
      </motion.p>
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.4 }}
      >
        <Link className="button" to="/">
          Back to dashboard
        </Link>
      </motion.div>
    </motion.div>
  );
}
